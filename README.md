# 📡 LLM YouTube Landscape Tracker v2.0

一個基於 AI 自動化的 YouTube 技術追蹤工具，專門監控全球頂尖 AI 研究者與開發者的最新動態。透過 LLM (Llama 3.3) 自動進行逐字稿分析、技術摘要提取與情感分析。

![GitHub Actions Status](https://img.shields.io/github/actions/workflow/status/benisnotitdog/llm-youtube-tracker/main.yml?label=Daily%20Update)
![License](https://img.shields.io/github/license/benisnotitdog/llm-youtube-tracker)

## 🌟 核心功能
- **自動監控**：每日自動追蹤 AI 領域頂尖頻道（如 AI Explained, Two Minute Papers, Fireship 等）。
- **智慧摘要**：利用 **Llama 3.3 (70B)** 模型針對影片內容進行繁體中文技術摘要，精準提取核心技術點。
- **逐字稿分析**：支援自動抓取 YouTube 逐字稿，並跨語言翻譯後交由 AI 分析。
- **動態網頁**：前端採用無框架輕量級設計，支援即時搜尋、日期排序與標籤過濾。
- **完全自動化**：透過 GitHub Actions 實現每日定時抓取、分析與自動部署。

## 🛠️ 技術架構
- **語言**: Python 3.10+
- **AI 模型**: Meta Llama 3.3 70B (via OpenRouter API)
- **資料來源**: YouTube Data API v3, YouTube Transcript API
- **前端**: HTML5 / CSS3 (Modern UI) / Vanilla JavaScript
- **部署**: GitHub Actions & GitHub Pages

## 📂 專案結構
```text
├── .github/workflows/  # GitHub Actions 定時執行腳本
├── docs/
│   ├── data.json       # AI 產出的結構化影片數據
│   └── index.html      # 追蹤器前端展示頁面
├── scraper.py          # 核心抓取與 LLM 分析程式
├── requirements.txt    # 相依套件清單