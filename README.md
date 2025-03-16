# 🚀 Automated YouTube Shorts Generator  

An **AI-powered web application** that automates the creation and uploading of **YouTube Shorts**. It generates unique quotes using **Gemini 2.0 Flash API**, overlays them on videos, adds trending background music, and uploads the final videos to YouTube automatically.  

## ✨ Features  
✅ **AI-Generated Unique Quotes** – Ensures originality using embeddings and similarity checks.  
✅ **Automated Video Creation** – Uses **FFmpeg** to generate high-quality **9:16** videos.  
✅ **Trending Music Integration** – Selects a **random trending song** with smooth fade-in/out effects.  
✅ **Multi-User YouTube Uploading** – Supports **multiple authenticated users** for automatic uploads.  
✅ **Flask Web App** – Provides two API routes:  
   - `/` – Generates and uploads a video.  
   - `/auth` – Authenticates a YouTube account for uploads.  
✅ **Fully Automated & Optimized** – Can be scheduled to generate and upload videos at intervals.  

## 📌 How It Works  
1. **Fetches Unique Quotes** – Calls the **Gemini API** to generate a meaningful, never-before-used quote.  
2. **Prevents Duplicates** – Uses **cosine similarity on embeddings** to filter out similar quotes.  
3. **Generates a Video** – Creates a **9:16 aspect ratio video** with the quote overlaid dynamically.  
4. **Adds Trending Music** – Picks a **random song** from a folder and syncs it with the video.  
5. **Uploads to YouTube** – Generates an **SEO-optimized title, description, and tags**, then uploads.  

## 🚀 Quick Start Guide  

### 1️⃣ **Clone the Repository**  
```bash
git clone https://github.com/ysr-hameed/Automate-Youtube-Video-Generate-and-Upload.git
cd Automate-Youtube-Video-Generate-and-Upload
python app.py
