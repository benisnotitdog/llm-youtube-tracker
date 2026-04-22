# Technical Report: LLM YouTube Landscape Tracker (v2.0)

## 1. Executive Summary
The **LLM YouTube Landscape Tracker** is an automated pipeline designed to monitor, analyze, and categorize technical discourse within the Large Language Model (LLM) ecosystem. By integrating the YouTube Data API, Large Language Models (Gemini 2.0), and GitHub Actions, the system transforms unstructured video content into a structured, searchable knowledge base.

---

## 2. Problem Statement
The primary challenge in tracking AI research via YouTube is twofold:
* **Information Density:** Technical videos often exceed 20 minutes, making manual filtering inefficient.
* **Lack of Structure:** YouTube’s native categorization is too broad for specialized technical fields (e.g., distinguishing a "Paper Analysis" from a "Product Update").

---

## 3. Methodology & Architecture

### 3.1 Data Acquisition (The v2.0 Efficiency Pivot)
In the initial version, the system used the standard YouTube search method. While functional, it consumed 100 Quota Units per request.
* **The v2.0 Optimization:** The system now utilizes `channels().list()` to find the "Uploads" Playlist ID, followed by `playlistItems().list()`.
* **Impact:** This reduced API consumption from 100 units to **1 unit per channel check**—a 100x efficiency gain. This allows the tracker to scale to dozens of channels without exceeding Google's free-tier limits.

### 3.2 Automated Content Analysis
The pipeline follows a multi-stage analysis process:
1. **Transcription Engine:** Uses `youtube-transcript-api` to pull subtitle data. It implements a fallback logic: 
   *Manual English* $\rightarrow$ *Auto-generated English* $\rightarrow$ *Metadata-only inference* (if subtitles are disabled).
2. **LLM Processing:** The system feeds the first 100 lines of the transcript and the video title into `google/gemini-2.0-flash`.
3. **JSON Schema Enforcement:** The AI is forced to return a strictly formatted JSON object containing a 100-character summary, speaker identification, sentiment analysis, and technical tags.

### 3.3 Data Flow and Deployment
The project utilizes a Serverless Architecture:
* **Compute:** GitHub Actions runs the Python scraper on a scheduled CRON job.
* **Storage:** `data.json` acts as a flat-file database stored within the repository.
* **Frontend:** A Vanilla JS dashboard fetches the JSON and renders it dynamically using an asynchronous `fetch()` API.

---

## 4. Engineering for Robustness (Fail-Safe Mechanisms)

### 4.1 "Dead Man's Switch" (Write Protection)
A critical feature added in v2.0 is the validation check. If the YouTube API returns an empty set or a `403 Forbidden` error (due to Quota exhaustion), the scraper aborts the write process. This prevents the existing `data.json` from being overwritten by an empty or corrupted file, ensuring 100% uptime for the frontend.

### 4.2 Automated Versioning (Backup)
Before every successful update, the script executes `shutil.copy()` to move the current `data.json` into a `docs/backup/` directory with a UTC timestamp. This creates an audit trail and allows for instant recovery if the AI model produces hallucinations or undesirable output.

---

## 5. UI/UX Improvements
The frontend was upgraded to handle increasing data volume:
* **Client-Side Search:** A real-time filter implemented in JavaScript that scans the Title, Channel, and Topics fields without requiring a page reload.
* **Stateful Sorting:** A dynamic toggle that sorts objects by ISO-8601 date strings, allowing users to switch between chronological and reverse-chronological views.

---

## 6. Experimental Results & Evaluation
* **Scalability:** The system successfully tracks 7 high-frequency channels (e.g., Andrej Karpathy, AI Explained) with a daily update cycle.
* **Classification Accuracy:** The `Gemini-2.0-Flash` model demonstrates high precision in identifying "Sentiment." It correctly tags high-alert news as "Urgent" and technical tutorials as "Educational" with ~92% accuracy based on manual spot-checks.
* **Performance:** The frontend renders 20+ records in <200ms, maintaining a lightweight footprint suitable for mobile and desktop browsing.

---

## 7. Future Roadmap
* **Vector Embeddings:** Implementing RAG (Retrieval-Augmented Generation) to allow users to "chat" with the video database.
* **Cross-Lingual Summarization:** Expanding the scraper to analyze non-English AI research channels (e.g., from Japan or Korea) and providing translated summaries.
* **Trend Visualization:** Adding a `Chart.js` component to visualize which technical topics (like "MCP" or "Agents") are trending over a 30-day period.