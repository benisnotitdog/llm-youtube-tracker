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
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {v["video_id"]: v for v in data}
        except: return {}
    return {}

def get_uploads_playlist_id(channel_id):
    """獲取頻道的『所有上傳影片』播放清單 ID (僅消耗 1 unit)"""
    res = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    return res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_smart_transcript(video_id):
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
    prompt = f"""
    分析這部 AI 影片：
    標題：{title}
    頻道：{channel}
    部分逐字稿：{transcript}
    
    請回傳 JSON 格式：
    {{
      "summary": "100字內中文核心摘要",
      "sentiment": "單詞情緒 (如 Analytical, Educational, Urgent)",
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
    
    try:
        for channel_name, channel_id in CHANNELS.items():
            print(f"正在檢查頻道: {channel_name}...")
            
            # 使用播放清單獲取，極度節省 Quota
            uploads_id = get_uploads_playlist_id(channel_id)
            res = youtube.playlistItems().list(
                playlistId=uploads_id,
                part="snippet",
                maxResults=5
            ).execute()

            for item in res.get("items", []):
                v_id = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]
                
                # 快取檢查
                if v_id in existing_data:
                    print(f"  - 跳過已存在的影片: {title[:30]}")
                    results.append(existing_data[v_id])
                    continue

                print(f"  + 分析新影片: {title[:30]}...")
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
                time.sleep(2)

        # --- 防呆與備份機制 ---
        if not results:
            print("⚠️ 錯誤：未獲取到任何數據，停止寫入以保護現有檔案。")
            return

        # 執行備份
        if os.path.exists(DATA_FILE):
            os.makedirs(BACKUP_DIR, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
            shutil.copy(DATA_FILE, f"{BACKUP_DIR}/data_{timestamp}.json")
            print(f"📦 已建立數據備份: data_{timestamp}.json")

        # 排序並寫入 docs/data.json
        results.sort(key=lambda x: x["published"], reverse=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✅ 成功更新 {len(results)} 部影片數據。")

    except Exception as e:
        print(f"❌ 執行過程中發生錯誤: {e}")

if __name__ == "__main__":
    run_scraper()