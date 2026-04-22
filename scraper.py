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

# 修改後的頻道清單
CHANNELS = {
    "Wes Roth":        "UCqCBQf6y16GuW55_88d6WkQ", # 替代 Karpathy，更新極快
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
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def get_smart_transcript(video_id):
    """
    優化後的字幕抓取：
    1. 優先找英文 2. 找不到則找任何語言並翻譯成英文 3. 失敗才回傳 None
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        try:
            # 優先嘗試找英文
            ts = transcript_list.find_transcript(['en'])
        except:
            # 若無英文，找第一個可用的語言並翻譯成英文
            first_ts = next(iter(transcript_list))
            ts = first_ts.translate('en')
            
        full_text = " ".join([x['text'] for x in ts.fetch()[:100]])
        return full_text
    except Exception as e:
        # 字幕不可用是常見現象，不中斷程式
        return None

def analyze_with_llm(title, channel, transcript):
    """
    使用 Llama 3.3 模型進行分析，並包含 JSON 格式清洗邏輯
    """
    has_transcript = transcript is not None
    content_context = transcript if has_transcript else "None (Only Title Available)"
    
    prompt = f"""
    請作為 AI 技術專家，分析以下影片並提供 JSON 格式的摘要。
    
    影片標題：{title}
    頻道：{channel}
    是否有逐字稿內容：{has_transcript}
    內容片段：{content_context}
    
    要求：
    1. 摘要必須使用「繁體中文」。
    2. 絕對不要用「這部影片介紹了」或「這部影片討論」開頭。
    3. 如果有逐字稿，請精煉核心技術點。
    4. 如果沒有逐字稿，請根據標題與頻道風格，推測最可能的技術亮點。
    5. summary 長度約 60-100 字。
    
    回傳格式 (純 JSON，不要包含 Markdown 標籤)：
    {{
      "summary": "...",
      "sentiment": "單個形容詞(英文)",
      "speaker": "人名或頻道名",
      "topics": ["英文標籤1", "英文標籤2"]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            # 使用 Llama 3.3 以避開 Google Gemini 的地區限制 (403)
            model="meta-llama/llama-3.3-70b-instruct", 
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        # 清洗 AI 可能回傳的 Markdown 語法 (如 ```json ... ```)
        raw_content = response.choices[0].message.content.strip()
        clean_content = raw_content
        if clean_content.startswith("```json"):
            clean_content = clean_content.replace("```json", "").replace("```", "").strip()
        elif clean_content.startswith("```"):
            clean_content = clean_content.replace("```", "").strip()
            
        return json.loads(clean_content)
    except Exception as e:
        print(f"  - AI 分析失敗 ({title[:20]}): {e}")
        return {
            "summary": "分析暫時不可用，請檢查 OpenRouter 配額或網路連線。",
            "sentiment": "Analytical",
            "speaker": channel,
            "topics": ["AI", "Tech"]
        }

def main():
    print(f"🚀 開始執行更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    existing_data = load_existing_data()
    existing_ids = {v['video_id'] for v in existing_data}
    results = existing_data.copy()
    new_count = 0

    for channel_name, channel_id in CHANNELS.items():
        print(f"正在檢查頻道: {channel_name}...")
        try:
            # 獲取播放清單 ID
            ch_resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
            if not ch_resp.get("items"):
                print(f"  - 找不到頻道 ID: {channel_id}")
                continue
                
            uploads_id = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # 抓取最新的 5 部影片
            playlist_resp = youtube.playlistItems().list(
                part="snippet", 
                playlistId=uploads_id, 
                maxResults=5
            ).execute()

            for item in playlist_resp.get("items", []):
                v_id = item["snippet"]["resourceId"]["videoId"]
                title = item["snippet"]["title"]

                # 如果影片已存在於 data.json 則跳過
                if v_id in existing_ids:
                    continue

                print(f"  + 處理新影片: {title[:30]}...")
                
                # 抓取並分析
                transcript = get_smart_transcript(v_id)
                analysis = analyze_with_llm(title, channel_name, transcript)

                video_entry = {
                    "video_id": v_id,
                    "channel": channel_name,
                    "title": title,
                    "published": item["snippet"]["publishedAt"][:10],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "url": f"[https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=){v_id}"
                }
                video_entry.update(analysis)
                results.append(video_entry)
                new_count += 1
                time.sleep(1) # 防禦性延遲

        except Exception as e:
            print(f"  - 處理頻道 {channel_name} 時發生異常: {e}")
            continue

    if new_count == 0:
        print("💡 沒有發現新影片，無需更新資料庫。")
        return

    # --- 儲存與備份 ---
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    
    if os.path.exists(DATA_FILE):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        shutil.copy(DATA_FILE, f"{BACKUP_DIR}/data_{ts}.json")

    # 按發佈日期排序 (由新到舊)
    results.sort(key=lambda x: x["published"], reverse=True)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ 更新完成! 本次新增 {new_count} 部影片，目前總計 {len(results)} 部。")

if __name__ == "__main__":
    main()