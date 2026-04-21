import os
import json
import time
import random
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATA_FILE = "docs/data.json"

CHANNELS = {
    "Andrej Karpathy": "UCnM4Q4I2H2HAcDmSV5E2ZfQ",
    "AI Explained":    "UCNJ1Ymd5yFuUPtn21xtRbbw",
    "Matthew Berman":  "UCnUYZLuoy1rq1aVMwx4aTzw",
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Fireship":        "UCsBjURrPoezykLs9EqgamOA",
}

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

def load_existing_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return {v["video_id"]: v for v in json.load(f)}
        except: return {}
    return {}

def get_latest_videos(channel_id, max_results=3):
    res = youtube.search().list(channelId=channel_id, part="snippet", order="date", maxResults=max_results, type="video").execute()
    return res.get("items", [])

def get_smart_transcript(video_id):
    # 在雲端執行時，稍微等待一下模擬真人行為
    time.sleep(random.uniform(2, 5))
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US'])
        full_text = " ".join([t['text'] for t in data])
        if len(full_text) > 9000:
            # 抽樣策略：頭 3000, 中 3000, 尾 3000 字
            mid = len(full_text) // 2
            return full_text[:3000] + "\n[...]\n" + full_text[mid-1500:mid+1500] + "\n[...]\n" + full_text[-3000:]
        return full_text
    except: return None

def analyze_with_llm(title, transcript):
    prompt = f"""Analyze this AI YouTube video.
Title: {title}
Transcript Excerpt: {transcript if transcript else "N/A (Analyze title only)"}

Output JSON format:
{{
  "speaker": "Identity of the speaker",
  "summary": "2-sentence key takeaway",
  "topics": ["topic1", "topic2"],
  "sentiment": "One word: Bullish, Skeptical, or Neutral + 1 reason",
  "references": ["Models/Papers/Channels mentioned"]
}}"""

    # 使用 Gemini 2.0 Flash Lite (免費且穩定)
    model_name = "google/gemini-2.0-flash-lite-preview-02-05:free"
    
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": "You are a senior AI researcher."},
                          {"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            if "429" in str(e):
                time.sleep(20) # 遇 429 等待長一點
            else: break
    return {"speaker": "N/A", "summary": "Error analyzing content.", "topics": [], "sentiment": "N/A", "references": []}

def run():
    existing_data = load_existing_data()
    results = []

    for channel_name, channel_id in CHANNELS.items():
        print(f"Checking: {channel_name}")
        videos = get_latest_videos(channel_id)
        for v in videos:
            v_id = v["id"]["videoId"]
            # 快取檢查：如果已經有這部影片且不是 Error，就跳過
            if v_id in existing_data and "Error" not in existing_data[v_id].get("summary", ""):
                print(f"  - Skipping {v_id} (Already exists)")
                results.append(existing_data[v_id])
                continue

            print(f"  + Processing: {v['snippet']['title'][:50]}...")
            transcript = get_smart_transcript(v_id)
            analysis = analyze_with_llm(v["snippet"]["title"], transcript)

            results.append({
                "video_id": v_id,
                "channel": channel_name,
                "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:10],
                "thumbnail": v["snippet"]["thumbnails"]["medium"]["url"],
                "url": f"https://www.youtube.com/watch?v={v_id}",
                **analysis # 展開 LLM 輸出的欄位
            })
            time.sleep(5) # 基礎節流

    os.makedirs("docs", exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Success! {len(results)} entries saved.")

if __name__ == "__main__":
    run()