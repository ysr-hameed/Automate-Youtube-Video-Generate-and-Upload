import os
import json
import random
import requests
import subprocess
from flask import Flask, jsonify, redirect, request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

app = Flask(__name__)

# Environment variables
API_KEY = os.getenv("GEMINI_API_KEY")
CLIENT_SECRETS_PATH = os.getenv("CLIENT_SECRETS_PATH")
TOKEN_FILE = os.getenv("TOKEN_FILE", "tokens.json")  # Path to store tokens
MUSIC_FOLDER = os.getenv("MUSIC_FOLDER", "trending_songs")
FONT_FILE = os.getenv("FONT_FILE", "Poppins-Regular.ttf")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "output.mp4")
CACHE_FILE = os.getenv("CACHE_FILE", "quotes_cache.txt")

# Vercel Redirect URI
REDIRECT_URI = "https://automate-youtube-video-generate-and-upload-3n3snevey.vercel.app/auth/callback"

# Ensure required files exist
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump([], f)

def fetch_unique_quote():
    """Fetch a unique quote from Gemini API."""
    payload = {
        "contents": [{"parts": [{"text": "Generate a unique, meaningful quote in 10-15 words."}]}],
        "generationConfig": {"temperature": 1.7, "maxOutputTokens": 50}
    }
    response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}", json=payload)
    
    quote = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()

    if not quote or not (10 <= len(quote.split()) <= 15):
        return fetch_unique_quote()  # Retry on failure

    # Avoid duplicates
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cached_quotes = set(f.read().splitlines())

        if quote in cached_quotes:
            return fetch_unique_quote()

    with open(CACHE_FILE, "a") as f:
        f.write(quote + "\n")

    return quote

def generate_video(quote):
    """Create a video using FFmpeg."""
    words = quote.split()
    lines, line = [], ""

    for word in words:
        if len(line) + len(word) <= 25:
            line += word + " "
        else:
            lines.append(line.strip())
            line = word + " "
    lines.append(line.strip())

    text_filters = []
    y_offset, font_size = 0.12, 65

    for line in lines:
        text_filters.append(
            f"drawtext=fontfile='{FONT_FILE}':text='{line}':fontcolor=white:fontsize={font_size}:x=w*0.05:y=h*{y_offset}:alpha='if(lt(t\\,1)\\,0\\,if(lt(t\\,2)\\,(t-1)/1\\,1))'"
        )
        y_offset += 0.065

    ffmpeg_command = f"""
    ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=10 -vf "{','.join(text_filters)}" -preset slow -crf 18 -c:v libx264 -t 10 {OUTPUT_FILE}
    """
    subprocess.run(ffmpeg_command, shell=True)

    music_file = get_random_song()
    if music_file:
        OUTPUT_WITH_AUDIO = "output_with_audio.mp4"
        ffmpeg_audio_command = f"""
        ffmpeg -y -i {OUTPUT_FILE} -i "{music_file}" -filter_complex "[1:a]afade=t=in:ss=0:d=2,afade=t=out:st=8:d=2[a1];[a1]volume=0.5[a2]" -map 0:v -map "[a2]" -shortest -preset slow -crf 18 -c:v libx264 -c:a aac -b:a 192k {OUTPUT_WITH_AUDIO}
        """
        subprocess.run(ffmpeg_audio_command, shell=True)
        os.replace(OUTPUT_WITH_AUDIO, OUTPUT_FILE)

def get_random_song():
    """Get a random song from the music folder."""
    if not os.path.exists(MUSIC_FOLDER):
        return None
    songs = [f for f in os.listdir(MUSIC_FOLDER) if f.endswith((".mp3", ".wav", ".aac", ".m4a"))]
    return os.path.join(MUSIC_FOLDER, random.choice(songs)) if songs else None

def authenticate_youtube(user_index):
    """Authenticate YouTube API."""
    if not os.path.exists(CLIENT_SECRETS_PATH):
        return None

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
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_PATH, scopes, redirect_uri=REDIRECT_URI)
        return redirect(flow.authorization_url()[0])

    return build("youtube", "v3", credentials=credentials)

def upload_video():
    """Upload video to YouTube."""
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
        if not youtube:
            continue

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
    """Generate title, description, and tags."""
    hashtags = ["#motivation", "#inspiration", "#success", "#mindset", "#hustle"]
    random.shuffle(hashtags)
    title = f"{quote[:40]}... {random.choice(hashtags)} {random.choice(hashtags)}"
    description = f"{quote}\n\n{random.choice(hashtags)} {random.choice(hashtags)} {random.choice(hashtags)}"
    tags = ",".join(hashtags[:3])
    return title, description, tags

@app.route("/")
def home():
    """Main route: Generate video and upload it."""
    quote = fetch_unique_quote()
    generate_video(quote)
    return upload_video()

@app.route("/auth")
def auth():
    """Redirect to Google's OAuth 2.0 flow."""
    return authenticate_youtube(len(json.load(open(TOKEN_FILE, "r"))))

@app.route("/auth/callback")
def auth_callback():
    """Handle OAuth 2.0 callback."""
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_PATH, ["https://www.googleapis.com/auth/youtube.upload"], redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=request.url)

    with open(TOKEN_FILE, "r+") as f:
        users = json.load(f) or []
        users.append(json.loads(flow.credentials.to_json()))
        f.seek(0)
        json.dump(users, f, indent=4)

    return "✅ Authentication successful!", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)