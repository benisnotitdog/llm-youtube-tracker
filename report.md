# LLM YouTube Landscape Tracker — Report

## Problem Statement
Tracking the rapidly evolving discourse around Large Language Models (LLMs) on YouTube is challenging due to the volume of content and the lack of structured categorization. This project automates the discovery, transcription, and categorization of LLM-focused YouTube videos to provide a clear, real-time overview of the landscape.

## Methodology
- **Data Collection**: The system uses the `google-api-python-client` to fetch the 5 most recent videos from 7 prominent AI-focused YouTube channels.
- **Transcription**: The `youtube-transcript-api` extracts closed captions. It prioritizes manual English captions, falls back to auto-generated ones, and utilizes auto-translation for non-English transcripts to ensure maximum coverage.
- **Summarisation & Tagging**: The project leverages the OpenRouter API (using `google/gemini-2.5-flash:free`) to process the transcripts or titles. The AI is prompted to generate a concise summary and categorize the video into structured tags (e.g., "Paper Analysis", "AI News").
- **Deployment**: Data is exported to `docs/data.json` and rendered via a lightweight vanilla HTML/JS frontend hosted on GitHub Pages. GitHub Actions is configured to run the scraper daily to keep the landscape tracker current.

## Evaluation Methods
- **Robustness**: The transcript extraction logic was evaluated against videos with disabled or non-English subtitles, ensuring graceful fallbacks (e.g., using video titles for inference).
- **Categorization Accuracy**: AI-generated tags are used to evaluate how well the system identifies relationships and themes across different creators.

## Experimental Results
- The tracker successfully bypassed transcript restrictions on multiple channels.
- The AI correctly categorized videos into themes, revealing that channels like Yannic Kilcher focus heavily on "Paper Analysis", while AI Explained leans towards "AI News" and "Model Benchmarking".
- The automated pipeline runs efficiently under free-tier API limits.