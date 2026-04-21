import os
import json
import time
import random
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

# 載入環境變數
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATA_FILE = "docs/data.json"

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
    """載入既有的數據以實現快取功能"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {v["video_id"]: v for v in data}
        except Exception as e:
            print(f"Loading existing data failed: {e}")
            return {}
    return {}

def get_latest_videos(channel_id, max_results=5):
    """獲取頻道最新的影片"""
    try:
        res = youtube.search().list(
            channelId=channel_id,
            part="snippet",
            order="date",
            maxResults=max_results,
            type="video"
        ).execute()
        return res.get("items", [])
    except Exception as e:
        print(f"Error fetching videos for {channel_id}: {e}")
        return []

def get_smart_transcript(video_id):
    """獲取字幕，若失敗則返回 None"""
    try:
        # 在 GitHub Actions 跑，通常不需要 cookies，但加個隨機延遲
        time.sleep(random.uniform(1, 3))
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
        full_text = " ".join([t['text'] for t in data])
        
        # 截斷過長的字幕以節省 Token (取頭、中、尾)
        if len(full_text) > 9000:
            mid = len(full_text) // 2
            return full_text[:3000] + "\n[...]\n" + full_text[mid-1500:mid+1500] + "\n[...]\n" + full_text[-3000:]
        return full_text
    except Exception:
        return None

def analyze_with_llm(title, transcript, retries=3):
    """使用 OpenRouter 分析影片內容，含重試機制"""
    content = transcript if transcript else "No transcript available. Analyze based on title only."
    
    prompt = f"""
    Analyze this YouTube video:
    Title: {title}
    Transcript: {content}

    Return a JSON object with:
    1. "summary": A 2-sentence concise summary.
    2. "topics": A list of 3-5 short tags (e.g., "AI News", "Coding").
    """

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-001", # 使用免費或穩定的模型
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            raw_res = response.choices[0].message.content
            # 確保解析 JSON 乾淨
            return json.loads(raw_res)
            
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait_time = (attempt + 1) * 20
                print(f"      [!] Rate limited (429). Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"      [!] LLM Error: {str(e)[:100]}")
            return {"summary": "Summary unavailable.", "topics": ["Error"]}

def run():
    existing_data = load_existing_data()
    results = []

    for channel_name, channel_id in CHANNELS.items():
        print(f"\nChecking: {channel_name}")
        videos = get_latest_videos(channel_id)
        
        for v in videos:
            v_id = v["id"]["videoId"]
            title = v["snippet"]["title"]
            
            # 快取邏輯：如果影片已存在且不是錯誤紀錄，就跳過
            if v_id in existing_data:
                old_v = existing_data[v_id]
                if "Error" not in old_v.get("summary", "") and "unavailable" not in old_v.get("summary", ""):
                    print(f"  - Skipping: {title[:50]} (Already exists)")
                    results.append(old_v)
                    continue

            print(f"  + Processing: {title[:50]}...")
            transcript = get_smart_transcript(v_id)
            analysis = analyze_with_llm(title, transcript)

            results.append({
                "video_id": v_id,
                "channel": channel_name,
                "title": title,
                "published": v["snippet"]["publishedAt"][:10],
                "thumbnail": v["snippet"]["thumbnails"]["medium"]["url"],
                "url": f"https://www.youtube.com/watch?v={v_id}",
                **analysis
            })
            
            # 每次 API 呼叫後基礎節流，避免觸發 429
            time.sleep(5)

    # 確保 docs 資料夾存在
    os.makedirs("docs", exist_ok=True)
    
    # 按照發布日期排序（新的在前）
    results.sort(key=lambda x: x["published"], reverse=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Done! Processed {len(results)} videos.")

if __name__ == "__main__":
    run()