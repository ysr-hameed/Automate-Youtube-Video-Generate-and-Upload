from flask import Flask, jsonify
import requests
import subprocess
import random
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = Flask(__name__)

# Define actual paths for necessary files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Use the script's directory
CACHE_FILE = os.path.join(BASE_DIR, "quotes_cache.txt")
FONT_FILE = os.path.join(BASE_DIR, "Poppins-Regular.ttf")
OUTPUT_FILE = os.path.join(BASE_DIR, "output.mp4")
MUSIC_FOLDER = os.path.join(BASE_DIR, "trending_songs")
TOKEN_FILE = os.path.join(BASE_DIR, "tokens.json")
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secrets.json")

# Ensure token file exists and is a valid JSON
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump([], f)

# Gemini API
API_KEY = "AIzaSyAjYzAiMu15hHve6g7qjTQA7IX9R60abW8"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def fetch_unique_quote():
    """Fetches a unique 10-15 word quote, avoiding repeats."""
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            f.write("")

    while True:
        payload = {
            "contents": [{"parts": [{"text": "Generate a unique, meaningful quote in 10-15 words."}]}],
            "generationConfig": {"temperature": 1.5, "maxOutputTokens": 50}
        }
        response = requests.post(f"{GEMINI_API_URL}?key={API_KEY}", json=payload)
        quote = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

        with open(CACHE_FILE, "r") as f:
            cached_quotes = set(f.read().splitlines())

        if 10 <= len(quote.split()) <= 15 and quote not in cached_quotes:
            with open(CACHE_FILE, "a") as f:
                f.write(quote + "\n")
            return quote

def generate_video(quote):
    """Creates a video with the quote displayed as text."""
    words = quote.split()
    lines = []
    line = ""

    for word in words:
        if len(line) + len(word) <= 25:
            line += word + " "
        else:
            lines.append(line.strip())
            line = word + " "
    lines.append(line.strip())

    text_filters = []
    y_offset = 0.12
    font_size = 65

    for line in lines:
        text_filters.append(
            f"drawtext=fontfile='{FONT_FILE}':text='{line}':fontcolor=white:fontsize={font_size}:x=w*0.05:y=h*{y_offset}:alpha='if(lt(t\\,1)\\,0\\,if(lt(t\\,2)\\,(t-1)/1\\,1))'"
        )
        y_offset += 0.065  

    ffmpeg_command = f"""
    ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=10 -vf "{','.join(text_filters)}" -preset slow -crf 18 -c:v libx264 -t 10 "{OUTPUT_FILE}"
    """
    subprocess.run(ffmpeg_command, shell=True)

    music_file = get_random_song()
    if music_file:
        output_with_audio = os.path.join(BASE_DIR, "output_with_audio.mp4")
        ffmpeg_audio_command = f"""
        ffmpeg -y -i "{OUTPUT_FILE}" -i "{music_file}" -filter_complex "[1:a]afade=t=in:ss=0:d=2,afade=t=out:st=8:d=2[a1];[a1]volume=0.5[a2]" -map 0:v -map "[a2]" -shortest -preset slow -crf 18 -c:v libx264 -c:a aac -b:a 192k "{output_with_audio}"
        """
        subprocess.run(ffmpeg_audio_command, shell=True)
        os.replace(output_with_audio, OUTPUT_FILE)

def get_random_song():
    """Returns a random song from the trending_songs folder."""
    if not os.path.exists(MUSIC_FOLDER):
        return None

    songs = [f for f in os.listdir(MUSIC_FOLDER) if f.endswith((".mp3", ".wav", ".aac", ".m4a"))]
    return os.path.join(MUSIC_FOLDER, random.choice(songs)) if songs else None

def authenticate_youtube(user_index):
    """Authenticates YouTube API for a given user index."""
    with open(TOKEN_FILE, "r") as f:
        try:
            users = json.load(f)
            if not isinstance(users, list):
                users = []
        except json.JSONDecodeError:
            users = []

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]

    if 0 <= user_index < len(users):
        credentials = Credentials.from_authorized_user_info(users[user_index], scopes)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes)
        credentials = flow.run_local_server(port=8080, open_browser=False)

        users.append(json.loads(credentials.to_json()))
        with open(TOKEN_FILE, "w") as f:
            json.dump(users, f, indent=4)

    return build("youtube", "v3", credentials=credentials)

def upload_video():
    """Uploads the generated video to YouTube for all authenticated users."""
    with open(TOKEN_FILE, "r") as f:
        try:
            users = json.load(f)
            if not isinstance(users, list):
                users = []
        except json.JSONDecodeError:
            users = []

    if not users:
        return "No authenticated users found. Run /auth first.", 400

    title, description, tags = generate_video_metadata(fetch_unique_quote())

    for i in range(len(users)):
        youtube = authenticate_youtube(i)

        request_body = {
            "snippet": {"title": title, "description": description, "tags": tags.split(","), "categoryId": "22"},
            "status": {"privacyStatus": "public"}
        }

        media_body = MediaFileUpload(OUTPUT_FILE, chunksize=-1, resumable=True, mimetype="video/*")

        request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media_body)

        response = None
        while response is None:
            status, response = request.next_chunk()

    return "✅ Video uploaded successfully!", 200

def generate_video_metadata(quote):
    """Generates a YouTube title, description, and tags based on the quote."""
    hashtags = ["#motivation", "#inspiration", "#success", "#mindset", "#hustle"]
    random.shuffle(hashtags)
    title = f"{quote[:40]}... {random.choice(hashtags)} {random.choice(hashtags)}"
    description = f"{quote}\n\n{random.choice(hashtags)} {random.choice(hashtags)} {random.choice(hashtags)}"
    tags = ",".join(hashtags[:3])
    return title, description, tags

@app.route("/")
def home():
    """Main route: Generates a video and uploads it to YouTube."""
    quote = fetch_unique_quote()
    generate_video(quote)
    return upload_video()

@app.route("/auth")
def auth():
    """Authentication route: Adds a new YouTube user for video uploads."""
    with open(TOKEN_FILE, "r") as f:
        try:
            users = json.load(f)
            if not isinstance(users, list):
                users = []
        except json.JSONDecodeError:
            users = []

    authenticate_youtube(len(users))
    return "✅ User authenticated successfully!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
