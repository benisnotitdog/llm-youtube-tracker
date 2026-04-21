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
        # 先列出該影片所有可用的字幕清單
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        try:
            # 優先找人工翻譯的英文或自動生成的英文字幕
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        except Exception:
            # 如果沒有英文，隨便抓第一個可用的字幕再翻譯成英文
            transcript = transcript_list.find_transcript(transcript_list._manually_created_transcripts.keys() or transcript_list._generated_transcripts.keys())
            transcript = transcript.translate('en')
            
        data = transcript.fetch()
        text = " ".join([t["text"] for t in data])
        return text[:5000] # 截取前 5000 字
    except Exception as e:
        print(f"      [!] Transcript error for {video_id}: {str(e)}")
        return None

def summarize(title, transcript):
    # 即便沒有 transcript，我們也可以單靠 Title 讓 AI 去猜測和總結，不要直接放棄！
    if not transcript:
        transcript_excerpt = "No transcript could be extracted. Please infer the content entirely based on the video title."
    else:
        transcript_excerpt = transcript

    prompt = f"""You are analyzing a YouTube video about Large Language Models (LLMs).
Video Title: {title}
Transcript Excerpt: {transcript_excerpt}

Task 1: In 2-3 sentences, summarize the specific models, techniques, or news covered. Focus strictly on what the creator actually discusses.
Task 2: Provide exactly 2-3 short, broad category tags that describe this video's relationship to the broader LLM ecosystem (e.g., "Paper Analysis", "AI News", "Coding & DevTools", "Model Benchmarking", "Ethics & Safety"). 

Format your response EXACTLY like this:
SUMMARY: <your summary here>
TAGS: <tag1>, <tag2>
"""
    
    try:
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash:free",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        
        # 拆解 AI 的回覆
        summary_part = "Failed to parse summary."
        tags_part = "Uncategorized"
        
        for line in content.split("\n"):
            if line.startswith("SUMMARY:"):
                summary_part = line.replace("SUMMARY:", "").strip()
            elif line.startswith("TAGS:"):
                tags_part = line.replace("TAGS:", "").strip()
                
        return summary_part, tags_part

    except Exception as e:
        return f"Error generating summary: {str(e)}", "Error"

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
            
            print(f"  > Processing: {title[:50]}...")

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