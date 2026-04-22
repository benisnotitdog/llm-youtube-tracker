import os
import json
import time
import datetime
import shutil
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

# 載入環境變數
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATA_FILE = "docs/data.json"
BACKUP_DIR = "docs/backup"

# 設定追蹤的頻道
CHANNELS = {
    "Andrej Karpathy": "UCnM4Q4I2H2HAcDmSV5E2ZfQ",
    "AI Explained":    "UCNJ1Ymd5yFuUPtn21xtRbbw",
    "Matthew Berman":  "UCnUYZLuoy1rq1aVMwx4aTzw",
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Fireship":        "UCsBjURrPoezykLs9EqgamOA",
}

# 初始化 API 客戶端
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

def load_existing_data():
    """載入既有數據以實現快取功能"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {v["video_id"]: v for v in data}
        except: return {}
    return {}

def get_uploads_playlist_id(channel_id):
    """獲取頻道的『所有上傳影片』播放清單 ID (消耗 1 unit)"""
    try:
        res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
        if "items" not in res or not res["items"]:
            return None
        return res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception as e:
        print(f"❌ 取得播放清單 ID 失敗 ({channel_id}): {e}")
        return None

def get_smart_transcript(video_id):
    """提取影片逐字稿"""
    try:
        ts_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            ts = ts_list.find_transcript(['en'])
        except:
            ts = ts_list.find_generated_transcript(['en'])
        return " ".join([x['text'] for x in ts.fetch()[:100]])
    except:
        return "No transcript available."

def analyze_with_llm(title, channel, transcript):
    """使用 AI 進行結構化分析"""
    prompt = f"""
    請分析這部 AI 技術影片並提供結構化摘要：
    標題：{title}
    頻道：{channel}
    部分逐字稿：{transcript}
    
    請務必回傳 JSON 格式：
    {{
      "summary": "100字內中文核心摘要",
      "sentiment": "單詞情緒 (例如 Analytical, Educational, Urgent)",
      "speaker": "主要講者名稱",
      "topics": ["標籤1", "標籤2", "標籤3"]
    }}
    """
    try:
        response = client.chat.completions.create(
            model="google/gemini-2.0-flash:free",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {
            "summary": "無法自動產生摘要",
            "sentiment": "Neutral",
            "speaker": channel,
            "topics": ["AI"]
        }

def run_scraper():
    existing_data = load_existing_data()
    results = []
    
    # 確保目錄存在
    os.makedirs("docs", exist_ok=True)

    for channel_name, channel_id in CHANNELS.items():
        print(f"正在檢查頻道: {channel_name}...")
        
        uploads_id = get_uploads_playlist_id(channel_id)
        if not uploads_id:
            print(f"  - 跳過頻道 {channel_name}，因為找不到上傳清單。")
            continue
        
        try:
            res = youtube.playlistItems().list(
                playlistId=uploads_id,
                part="snippet",
                maxResults=5
            ).execute()

            items = res.get("items", [])
            for item in items:
                v_id = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]
                
                # 快取檢查：如果已分析過，直接沿用舊數據
                if v_id in existing_data:
                    print(f"  - 跳過已存在的影片: {title[:20]}...")
                    results.append(existing_data[v_id])
                    continue

                print(f"  + 正在分析新影片: {title[:20]}...")
                transcript = get_smart_transcript(v_id)
                analysis = analyze_with_llm(title, channel_name, transcript)

                video_entry = {
                    "video_id": v_id,
                    "channel": channel_name,
                    "title": title,
                    "published": item["snippet"]["publishedAt"][:10],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "url": f"https://www.youtube.com/watch?v={v_id}"
                }
                video_entry.update(analysis)
                results.append(video_entry)
                time.sleep(1) 

        except Exception as e:
            print(f"  - 抓取頻道影片時發生錯誤: {e}")
            continue

    # --- 最終寫入與保護機制 ---
    if not results:
        print("⚠️ 錯誤：本次執行未獲得任何影片數據，中止寫入。")
        return

    # 備份舊檔案
    if os.path.exists(DATA_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        shutil.copy(DATA_FILE, f"{BACKUP_DIR}/data_{timestamp}.json")
        print(f"📦 已建立數據備份: {BACKUP_DIR}/data_{timestamp}.json")

    # 排序並儲存
    results.sort(key=lambda x: x["published"], reverse=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 成功更新資料，目前共累積 {len(results)} 部影片。")

if __name__ == "__main__":
    run_scraper()