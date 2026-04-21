import os
import json
import time
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
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)
        try:
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
            except Exception:
                # 取第一個可用的字幕
                transcript = next(iter(transcript_list))
        data = transcript.fetch()
        text = " ".join([t.text for t in data])
        return text[:5000]
    except Exception as e:
        print(f"      [!] Transcript error for {video_id}: {str(e)[:80]}")
        return None

def summarize(title, transcript):
    if not transcript:
        transcript_excerpt = "No transcript available. Infer from title only."
    else:
        transcript_excerpt = transcript

    prompt = f"""You are analyzing a YouTube video about AI and Large Language Models (LLMs).
Video Title: {title}
Transcript Excerpt: {transcript_excerpt}

Task 1: In 2-3 sentences, summarize the specific models, techniques, or news covered.
Task 2: Provide exactly 2-3 short category tags (e.g., "Paper Analysis", "AI News", "Coding & DevTools", "Model Benchmarking", "Ethics & Safety", "Model Release").

Format EXACTLY like this (no extra text):
SUMMARY: <your summary here>
TAGS: <tag1>, <tag2>
"""

    for attempt in range(3):  # 最多重試3次
        try:
            time.sleep(10)  # 每次呼叫前等10秒，確保不超過rate limit
            response = client.chat.completions.create(
                model="mistralai/mistral-7b-instruct:free",  # 備用免費模型
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content.strip()

            summary_part = "No summary available."
            tags_part = "General LLM"

            for line in content.split("\n"):
                if line.startswith("SUMMARY:"):
                    summary_part = line.replace("SUMMARY:", "").strip()
                elif line.startswith("TAGS:"):
                    tags_part = line.replace("TAGS:", "").strip()

            return summary_part, tags_part

        except Exception as e:
            err = str(e)
            if "429" in err:
                print(f"      [!] Rate limited, waiting 30s before retry {attempt+1}/3...")
                time.sleep(30)
            else:
                print(f"      [!] Summarize error: {err[:80]}")
                return "Error generating summary.", "Error"

    return "Rate limit exceeded after retries.", "Error"

def run():
    results = []
    for channel_name, channel_id in CHANNELS.items():
        print(f"\nFetching: {channel_name}")
        videos = get_latest_videos(channel_id)
        for v in videos:
            video_id = v["id"]["videoId"]
            title = v["snippet"]["title"]
            published = v["snippet"]["publishedAt"]
            thumbnail = v["snippet"]["thumbnails"]["medium"]["url"]
            url = f"https://www.youtube.com/watch?v={video_id}"

            print(f"  > {title[:60]}")
            transcript = get_transcript(video_id)
            summary, topics = summarize(title, transcript)

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

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Done! {len(results)} videos saved to docs/data.json")

if __name__ == "__main__":
    run()