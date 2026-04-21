import os
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from openai import OpenAI

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

CHANNELS = {
    "Andrej Karpathy": "UCnM4Q4I2H2HAcDmSV5E2ZfQ",
    "Yannic Kilcher":  "UCZHmQk67mSJgfCCTn7xBfew",
    "AI Explained":    "UCNJ1Ymd5yFuUPtn21xtRbbw",
    "Matthew Berman":  "UCnUYZLuoy1rq1aVMwx4aTzw",
    "Wes Roth":        "UCnngBXXAFEFCFsUNxDyVHKA",
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "Fireship":        "UCsBjURrPoezykLs9EqgamOA",
}

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# 初始化 OpenRouter 客戶端
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def get_latest_videos(channel_id, max_results=5):
    res = youtube.search().list(
        channelId=channel_id,
        part="snippet",
        order="date",
        maxResults=max_results,
        type="video"
    ).execute()
    return res.get("items", [])

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t["text"] for t in transcript])
        return text[:4000] # 截取前4000字避免超過長度限制
    except Exception:
        return None

def summarize(title, transcript):
    if not transcript:
        return "No transcript available."
    prompt = f"""YouTube video title: {title}
Transcript excerpt: {transcript}

In 2-3 sentences, summarize what LLM topics are discussed. Mention specific models, techniques, or concepts covered."""
    
    try:
        # 使用 OpenRouter 的完全免費 Gemini 模型
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash:free",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def extract_topics(summary):
    keywords = ["GPT", "Claude", "Gemini", "LLaMA", "Mistral", "RAG",
                "fine-tuning", "prompt", "agent", "transformer", "RLHF",
                "inference", "benchmark", "multimodal", "open-source"]
    found = [k for k in keywords if k.lower() in summary.lower()]
    return ", ".join(found) if found else "General LLM"

def run():
    results = []
    for channel_name, channel_id in CHANNELS.items():
        print(f"Fetching: {channel_name}")
        videos = get_latest_videos(channel_id)
        for v in videos:
            video_id = v["id"]["videoId"]
            title = v["snippet"]["title"]
            published = v["snippet"]["publishedAt"]
            thumbnail = v["snippet"]["thumbnails"]["medium"]["url"]
            url = f"https://www.youtube.com/watch?v={video_id}"

            transcript = get_transcript(video_id)
            summary = summarize(title, transcript)
            topics = extract_topics(summary)

            results.append({
                "video_id": video_id,
                "channel": channel_name,
                "title": title,
                "published": published[:10],
                "summary": summary,
                "topics": topics,
                "thumbnail": thumbnail,
                "url": url
            })
            print(f"  ✓ {title[:60]}")

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done! {len(results)} videos saved to docs/data.json")

if __name__ == "__main__":
    run()