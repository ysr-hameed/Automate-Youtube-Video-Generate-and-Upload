import os
import json
import random
import requests
import subprocess
from flask import Flask, redirect, request, session, url_for
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request


app = Flask(__name__)
app.secret_key = "your_secret_key"

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(BASE_DIR, "Poppins-Regular.ttf")
OUTPUT_FILE = os.path.join(BASE_DIR, "output.mp4")
MUSIC_FOLDER = os.path.join(BASE_DIR, "trending_songs")
TOKEN_FILE = os.path.join(BASE_DIR, "tokens.json")
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secrets.json")

# Google API settings
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
REDIRECT_URI = "https://ysrautomation.pythonanywhere.com/auth/callback"

# Ensure token file exists
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump({}, f)

# ** Step 1: Authenticate with YouTube **
@app.route("/auth")
def authenticate_youtube():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state
    return redirect(authorization_url)

# ** Step 2: Handle Google Callback & Save Token **
@app.route("/auth/callback")
def auth_callback():
    state = session.get("state")
    if not state:
        return "❌ Authentication failed: Missing state."

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI, state=state
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    with open(TOKEN_FILE, "w") as f:
        json.dump(json.loads(credentials.to_json()), f, indent=4)

    return redirect(url_for("automate"))






def get_credentials():
    """Get the user's credentials from the storage or create a new one."""
    credentials = None
    
    # Path to the tokens.json file containing OAuth2 credentials
    credentials_file = 'tokens.json'
    
    # Check if credentials file exists and load it
    if os.path.exists(credentials_file):
        # Load credentials from the file (this assumes you saved them previously)
        credentials = Credentials.from_authorized_user_file(credentials_file)
    
    # If no credentials are available or the credentials have expired
    if not credentials or credentials.expired:
        if credentials and credentials.expired and credentials.refresh_token:
            # Refresh the expired credentials using the refresh token
            credentials.refresh(Request())
        else:
            # Handle the case where credentials are missing or not refreshed
            # You should implement a flow to ask the user to reauthorize the app
            raise Exception("No valid credentials available. Please reauthorize.")
    
    # Save the refreshed credentials back to the file for later use
    with open(credentials_file, 'w') as token:
        token.write(credentials.to_json())
    
    return credentials
    
def fetch_unique_quote():
    try:
        # Make the GET request with SSL verification bypassed
        response = requests.get("https://api.quotable.io/random", verify=False)  # Disables SSL verification

        # Check if the response status code is OK (200)
        if response.status_code == 200:
            data = response.json()
            return data["content"], data["author"]
        else:
            return "Error fetching quote", "Unknown"
    except requests.exceptions.RequestException as e:
        # Catch any other request exceptions (like timeout, connection errors, etc.)
        return f"Error fetching quote: {str(e)}", "Unknown"

# Example usage
quote, author = fetch_unique_quote()
print(f'"{quote}" - {author}')

# ** Step 5: Generate Video with Text Overlay **  
def generate_video(quote, author):  
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
    y_offset = 0.12  # Starting Y offset for the quote

    # Effect for fade-in start: Zoom-in effect (scale up)
    fade_in_effect = "[0:v]scale=iw*1.1:ih*1.1,zoompan=z='if(gte(pzoom\,1.0)\,1.0\,pzoom+0.02)':s=1080x1920:d=200"  
  
    # Generate the quote lines
    for line in lines:  
        text_filters.append(  
            f"drawtext=fontfile='{FONT_FILE}':text='{line}':fontcolor=white:fontsize=65:x=w*0.10:y=h*{y_offset}:alpha='if(lt(t\\,1)\\,0\\,if(lt(t\\,2)\\,(t-1)/1\\,1))'"  
        )  
        y_offset += 0.065  # Adjusting the space for the next line
  
    # Adjust y_offset for the author's name to be below the last quote line
    author_text = f"~ {author}"
    
    # Handle long author name (break into multiple lines if needed)
    max_line_length = 25  # Max characters per line for the author's name
    author_lines = []
    while len(author_text) > max_line_length:
        split_index = author_text.rfind(' ', 0, max_line_length)
        if split_index == -1:  # No space found, break the word
            split_index = max_line_length
        author_lines.append(author_text[:split_index])
        author_text = author_text[split_index:].strip()
    author_lines.append(author_text)
    
    # Add the author lines to the filters
    author_y_offset = y_offset + 0.065  # Adding extra space below the last quote line
    for i, line in enumerate(author_lines):
        text_filters.append(  
            f"drawtext=fontfile='{FONT_FILE}':text='{line}':fontcolor=white:fontsize=50:x=w*0.5-text_w/2:y=h*{author_y_offset + 0.065*i}:alpha='if(lt(t\\,1)\\,0\\,if(lt(t\\,2)\\,(t-1)/1\\,1))'"  
        )
    
    # FFmpeg command to generate the video (7 seconds, zoom-in effect)
    ffmpeg_command = f"""  
    ffmpeg -y -f lavfi -i color=c=black:s=1080x1920:d=7 -vf "{fade_in_effect},{','.join(text_filters)}" -preset slow -crf 18 -c:v libx264 -t 7 {OUTPUT_FILE}  
    """  
    subprocess.run(ffmpeg_command, shell=True)  
  
    # Handle background music if available
    music_file = get_random_song()  
    if music_file:  
        OUTPUT_WITH_AUDIO = os.path.join(BASE_DIR, "output_with_audio.mp4")  
        ffmpeg_audio_command = f"""  
        ffmpeg -y -i {OUTPUT_FILE} -i "{music_file}" -filter_complex "[1:a]afade=t=in:ss=0:d=2,afade=t=out:st=6:d=2[a1];[a1]volume=0.5[a2]" -map 0:v -map "[a2]" -shortest -preset slow -crf 18 -c:v libx264 -c:a aac -b:a 192k {OUTPUT_WITH_AUDIO}  
        """  
        subprocess.run(ffmpeg_audio_command, shell=True)  
        os.replace(OUTPUT_WITH_AUDIO, OUTPUT_FILE)  

    # Adding fade-out effect before the last second of video (for quote and author)
    fade_out_effect = f"fade=t=out:st=6:d=1"  # Fade-out starting at 6 seconds, lasts 1 second

    # Update final video with fade-out effect for both quote and author
    ffmpeg_final_command = f"""
    ffmpeg -y -i {OUTPUT_FILE} -vf "{fade_out_effect}" -preset slow -crf 18 -c:v libx264 -t 7 {OUTPUT_FILE}
    """
    subprocess.run(ffmpeg_final_command, shell=True)

# ** Step 6: Get a Random Trending Song **
def get_random_song():
    songs = [f for f in os.listdir(MUSIC_FOLDER) if f.endswith((".mp3", ".wav", ".aac", ".m4a"))]
    return os.path.join(MUSIC_FOLDER, random.choice(songs)) if songs else None

# ** Step 7: Upload Video to YouTube **
@app.route("/")
def automate():
    credentials = get_credentials()
    if not credentials:
        return "❌ No authentication found. Please <a href='/auth'>authenticate here</a>."

    youtube = build("youtube", "v3", credentials=credentials)

    quote, author = fetch_unique_quote()
    generate_video(quote, author)

    viral_tags = [
        # Core Motivation & Success Hashtags
        "motivation", "inspiration", "success", "mindset", "hustle", "grind", "lifequotes",
        "wisdom", "selfgrowth", "entrepreneur", "positivity", "focus", "leadership", "vision",
        "goals", "selfmade", "dreambig", "wealth", "powerful", "neverquit", "believe", "attitude",
        "selfdiscipline", "winner", "happiness", "hustlemode", "quotesdaily", "billionairemindset",
        
        # High-Engagement Hashtags
        "determination", "mentality", "ambition", "growth", "motivationmonday", "successquotes",
        "hardwork", "stayfocused", "selfimprovement", "businessquotes", "dreamchaser", "dedication",
        "mindsetmatters", "grindmode", "nevergiveup", "unstoppable", "selfdevelopment", "greatness",
        "millionairemindset", "bossmindset", "successdriven", "manifestation", "entrepreneurmindset",
        "moneyquotes", "businessmotivation", "mindovermatter", "goalsetter", "disciplineequalsfreedom",
        "riseandgrind", "growthmindset", "winnersmindset", "selfgrowthjourney", "hustleharder",
        "betteryourself", "motivationalquotes", "grinddontstop", "successtips", "positivemindset",
        "manifestyourdreams", "goaldigger", "neverbackdown", "winnersneverquit", "personaldevelopment",
        "dreambigworkhard", "entrepreneurlifestyle", "inspirationalquotes", "driventosucceed",
        "hustlersambition", "wealthmindset", "powerofpositivity", "businessmindset", "believeinyourself",
        "passionandpurpose", "selfbelief", "workethic", "staymotivated", "keeppushing", "pushyourself",
        "levelup", "buildyourempire", "createthelifeyouwant", "nothingisimpossible", "workhardstayhumble",
        "positivevibes", "strongmind", "beyourownboss", "noexcuses", "hustleandflow", "successiskey",
        "keepgoing", "nevergiveupquotes", "fearless", "becomebetter", "inspiredaily", "selfconfidence",
        "highperformance", "staydriven", "motivationalmindset", "thinkandgrowrich", "powerthoughts",
        "buildyourdreams", "focusedandfearless", "goaloriented", "unstoppablemindset", "hustlersmindset",

        # Trending & Viral Hashtags
        "millionairelifestyle", "richmindset", "growthquotes", "lawofattraction", "powerofmindset",
        "financialfreedom", "dreambigger", "stayhungry", "businessgrowth", "grindhustle", "goalcrusher",
        "dailyquotes", "wealthyhabits", "unstoppableforce", "focusonyourgoals", "highperformancehabits",
        "millionairesecrets", "alphamentality", "investinyourself", "innerpower", "hardworkpaysoff",
        "wintheday", "winningmentality", "lifesuccess", "nevergiveupmindset", "billionairelifestyle",
        "getmotivated", "mindsetcoach", "yourfuture", "gamechanger", "levelupmindset", "keepmovingforward",
        "bossmoves", "moneytalks", "stayrelentless", "selfmastery", "createyourfuture", "neversettle","grindhard", "selfmadebillionaire", "successmindset", "goalsetter", "neversettle", "riseandshine",
    "worksmart", "entrepreneurialmindset", "chasingdreams", "positivethinking", "unstoppableforce",
    "neverstopdreaming", "ambitioniskey", "getthingsdone", "keepgrinding", "motivationalmindset",
    "hustletime", "dreamchasers", "workhardstayhumble", "workforit", "achievegreatness", "inspireothers"
    ]

    # Randomly pick 10-15 viral tags
    tags = random.sample(viral_tags, random.randint(10, 15))

    video_title = f'"{quote}" - {author} #motivation #success #hustle'
    video_description = f"{quote}\n\nThis is your daily dose of motivation. Never stop believing in yourself! #motivation #inspiration #success #mindset #growth"

    # Upload video to YouTube
    video_request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": video_title,
                "description": video_description,
                "tags": tags
            },
            "status": {
                "privacyStatus": "public"
            }
        },
        media_body=MediaFileUpload(OUTPUT_FILE, mimetype="video/mp4")
    )
    
    video_response = video_request.execute()

    return "✅ Video uploaded successfully!"

if __name__ == "__main__":
    app.run(debug=True)