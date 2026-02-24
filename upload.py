import os
import requests
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN")
COOKIE_PATH = os.getenv("COOKIE_PATH", str(Path.home() / "cookies.txt"))

UPLOADED_FILE = Path("uploaded.txt")

# ---------------- helpers ----------------

def is_already_uploaded(video_id: str) -> bool:
    if not UPLOADED_FILE.exists():
        return False
    return video_id in UPLOADED_FILE.read_text().splitlines()

def mark_as_uploaded(video_id: str):
    with UPLOADED_FILE.open("a") as f:
        f.write(video_id + "\n")

def delete_video(file_path: str):
    try:
        Path(file_path).unlink(missing_ok=True)
        print(f"Deleted local video file: {file_path}")
    except Exception as e:
        print("Failed to delete file:", e)

# ---------------- youtube ----------------

def get_latest_video():
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={YOUTUBE_CHANNEL_ID}"
        "&order=date&maxResults=1&type=video"
        f"&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["items"][0]

# ---------------- download ----------------

def download_video(video_id: str) -> str:
    if is_already_uploaded(video_id):
        print(f"Video {video_id} already uploaded. Skipping.")
        exit(0)

    ydl_opts = {
        "cookies": COOKIE_PATH,
        "outtmpl": f"video-{video_id}.%(ext)s",
        "format": "bv*[ext=mp4]+ba/b[ext=mp4]/best",
        "merge_output_format": "mp4",
        "verbose": True,

        # same fixes you used in Node
        "js_runtime": "node",
        "remote_components": {"ejs": "github"},
        "no_cache_dir": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}",
            download=True,
        )
        file_path = ydl.prepare_filename(info)

    mark_as_uploaded(video_id)
    return file_path

# ---------------- facebook ----------------

def upload_to_facebook(file_path: str, title: str, description: str):
    url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos"

    with open(file_path, "rb") as f:
        files = {"source": f}
        data = {
            "description": f"{title}\n\n{description}",
            "access_token": FB_PAGE_TOKEN,
        }

        r = requests.post(url, files=files, data=data)
        if not r.ok:
            raise RuntimeError(f"Upload failed: {r.text}")

        print("Video uploaded successfully:", r.json())

# ---------------- main ----------------

def main():
    video = get_latest_video()
    video_id = video["id"]["videoId"]
    title = video["snippet"]["title"]
    description = video["snippet"]["description"]

    file_path = download_video(video_id)
    upload_to_facebook(file_path, title, description)
    delete_video(file_path)

if __name__ == "__main__":
    main()