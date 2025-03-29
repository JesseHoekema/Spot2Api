import os
import uuid
import threading
import time
from flask import Flask, send_file, jsonify, request
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp

app = Flask(__name__)

# Configuration
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Store download status
downloads = {}

# Initialize Spotify client - you need to fill in your credentials

spotify = spotipy.Spotify(
    client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

@app.route('/download', methods=['POST'])
def download_track():
    data = request.json
    if not data or 'spotify_url' not in data:
        return jsonify({"error": "Missing spotify_url parameter"}), 400
    
    spotify_url = data['spotify_url']
    download_id = str(uuid.uuid4())
    
    # Store download information
    downloads[download_id] = {
        "status": "processing",
        "url": spotify_url,
        "file_path": None,
        "timestamp": time.time()
    }
    
    # Start download in background
    threading.Thread(target=process_download, args=(spotify_url, download_id)).start()
    
    return jsonify({
        "id": download_id,
        "status": "processing",
        "status_url": f"/status/{download_id}"
    })

def process_download(spotify_url, download_id):
    try:
        # Extract track ID from Spotify URL
        track_id = spotify_url.split('/')[-1].split('?')[0]
        
        # Get track information from Spotify API
        track_info = spotify.track(track_id)
        artist = track_info['artists'][0]['name']
        track_name = track_info['name']
        search_query = f"{artist} - {track_name}"
        
        # Create a safe filename
        safe_filename = "".join([c for c in search_query if c.isalpha() or c.isdigit() or c in "- "]).rstrip()
        file_path = os.path.join(DOWNLOAD_FOLDER, f"{download_id}_{safe_filename}.mp3")
        
        # Setup yt-dlp options
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': file_path.replace('.mp3', ''),
            'quiet': True,
            'no_warnings': True,
        }
        
        # Search for the track on YouTube and download it
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_term = f"ytsearch:{search_query} audio"
            info = ydl.extract_info(search_term, download=True)
            
            # The file will be named [file_path].mp3 after conversion
            final_file_path = f"{file_path.replace('.mp3', '')}.mp3"
            
            # Update download status
            downloads[download_id]["status"] = "completed"
            downloads[download_id]["file_path"] = final_file_path
            downloads[download_id]["filename"] = f"{safe_filename}.mp3"
    
    except Exception as e:
        downloads[download_id]["status"] = "failed"
        downloads[download_id]["error"] = str(e)

@app.route('/status/<download_id>', methods=['GET'])
def check_status(download_id):
    if download_id not in downloads:
        return jsonify({"error": "Download ID not found"}), 404
    
    download_info = downloads[download_id]
    response = {
        "id": download_id,
        "status": download_info["status"],
        "url": download_info["url"]
    }
    
    if download_info["status"] == "completed":
        response["mp3_url"] = f"/mp3/{download_id}"
    elif download_info["status"] == "failed":
        response["error"] = download_info.get("error", "Unknown error")
    
    return jsonify(response)

@app.route('/mp3/<download_id>', methods=['GET'])
def get_mp3(download_id):
    if download_id not in downloads:
        return jsonify({"error": "Download ID not found"}), 404
    
    download_info = downloads[download_id]
    if download_info["status"] != "completed":
        return jsonify({"error": "Download not completed yet"}), 400
    
    # Send the file
    return send_file(
        download_info["file_path"],
        as_attachment=True,
        download_name=download_info.get("filename", "track.mp3"),
        mimetype="audio/mpeg"
    )

# Cleanup route for old downloads
@app.route('/cleanup', methods=['POST'])
def cleanup_old_downloads():
    # Remove downloads older than 1 hour
    current_time = time.time()
    removed = 0
    
    for download_id in list(downloads.keys()):
        download_info = downloads[download_id]
        if download_info.get("timestamp", 0) < current_time - 3600:  # 1 hour
            if download_info.get("file_path") and os.path.exists(download_info["file_path"]):
                os.remove(download_info["file_path"])
            del downloads[download_id]
            removed += 1
    
    return jsonify({"message": f"Cleaned up {removed} old downloads"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2354, debug=True)