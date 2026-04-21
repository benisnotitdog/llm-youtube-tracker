import os
import json
import time
import random
import re
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
        except:
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
        print(f"Error fetching videos: {e}")
        return []

def get_smart_transcript(video_id):
    """精確抓取前、中、後段逐字稿，優化 Token 並保留關鍵資訊"""
    try:
        time.sleep(random.uniform(1, 2))
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
        
        if len(data) <= 150:
            return " ".join([t['text'] for t in data])

        mid = len(data) // 2
        head = " ".join([t['text'] for t in data[:50]])
        body = " ".join([t['text'] for t in data[mid-25:mid+25]])
        tail = " ".join([t['text'] for t in data[-50:]])
        
        return f"[START]\n{head}\n[MIDDLE]\n{body}\n[END]\n{tail}"
    except:
        return None

def analyze_with_llm(title, channel_name, transcript, retries=3):
    """使用 OpenRouter 分析內容，具備 JSON 格式校正與異常處理"""
    content = transcript if transcript else "No transcript available. Use title/channel only."
    
    prompt = f"""
    You are an expert AI news analyst. Analyze this YouTube video from the channel '{channel_name}'.
    
    VIDEO DATA:
    Title: {title}
    Channel: {channel_name}
    Transcript Snippets: {content}

    TASK:
    Return ONLY a JSON object with:
    1. "speaker": Person name (if unknown, use '{channel_name}').
    2. "summary": A 2-sentence concise summary in Traditional Chinese.
    3. "sentiment": Analyze the tone (e.g., "Excited/Optimistic", "Critical/Warning", "Educational/Neutral").
    4. "topics": A list of 3-5 tags in English.
    """

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            raw_res = response.choices[0].message.content
            clean_res = re.sub(r"```json|```", "", raw_res).strip()
            data = json.loads(clean_res)
            
            # 確保回傳是字典而非列表
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            if not isinstance(data, dict):
                raise ValueError("Format error")
                
            return data
            
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait_time = (attempt + 1) * 20
                print(f"      [!] Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            print(f"      [!] Analysis logic error: {str(e)[:50]}")
            
    # 最後的保底方案
    return {
        "speaker": channel_name, 
        "summary": "分析處理中或暫時無法產生摘要。", 
        "sentiment": "Neutral", 
        "topics": ["AI News"]
    }

def run():
    existing_data = load_existing_data()
    results = []

    for channel_name, channel_id in CHANNELS.items():
        print(f"\nChecking: {channel_name}")
        videos = get_latest_videos(channel_id)
        
        for v in videos:
            v_id = v["id"]["videoId"]
            title = v["snippet"]["title"]
            
            # 只有在摘要正常時才跳過，否則重新分析
            if v_id in existing_data:
                old_v = existing_data[v_id]
                if "無法產生" not in old_v.get("summary", "") and "Error" not in old_v.get("summary", ""):
                    print(f"  - Skipping: {title[:40]}")
                    results.append(old_v)
                    continue

            print(f"  + Analyzing: {title[:40]}...")
            transcript = get_smart_transcript(v_id)
            analysis = analyze_with_llm(title, channel_name, transcript)

            # 建立基礎資訊字典
            video_entry = {
                "video_id": v_id,
                "channel": channel_name,
                "title": title,
                "published": v["snippet"]["publishedAt"][:10],
                "thumbnail": v["snippet"]["thumbnails"]["medium"]["url"],
                "url": f"https://www.youtube.com/watch?v={v_id}"
            }
            
            # 合併 AI 分析結果
            video_entry.update(analysis)
            results.append(video_entry)
            
            time.sleep(5)

    os.makedirs("docs", exist_ok=True)
    results.sort(key=lambda x: x["published"], reverse=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Finished! Database updated with {len(results)} videos.")

if __name__ == "__main__":
    run()