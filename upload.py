import os
import sys
import shutil
import requests
import yt_dlp
from pathlib import Path
from dotenv import load_dotenv

# ---------------- env ----------------

load_dotenv()

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val

YOUTUBE_API_KEY = require_env("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = require_env("YOUTUBE_CHANNEL_ID")
FB_PAGE_ID = require_env("FB_PAGE_ID")
FB_PAGE_TOKEN = require_env("FB_PAGE_TOKEN")

COOKIE_PATH = os.getenv("COOKIE_PATH", "./cookies.txt")
COOKIE_PATH = Path(COOKIE_PATH)

UPLOADED_FILE = Path("uploaded.txt")

# ---------------- sanity checks ----------------

if not shutil.which("node"):
    raise RuntimeError("Node.js not found in PATH (required by yt-dlp)")

if not COOKIE_PATH.exists():
    raise RuntimeError(f"cookies.txt not found at {COOKIE_PATH}")

# ---------------- helpers ----------------

def is_already_uploaded(video_id: str) -> bool:
    if not UPLOADED_FILE.exists():
        return False
    return video_id in UPLOADED_FILE.read_text().splitlines()

def mark_as_uploaded(video_id: str):
    UPLOADED_FILE.write_text(
        UPLOADED_FILE.read_text() + video_id + "\n"
        if UPLOADED_FILE.exists()
        else video_id + "\n"
    )

def delete_video(file_path: str):
    try:
        Path(file_path).unlink(missing_ok=True)
        print(f"Deleted local video file: {file_path}")
    except Exception as e:
        print("Failed to delete file:", e)

def resolve_downloaded_file(video_id: str) -> str:
    for f in Path(".").iterdir():
        if f.name.startswith(f"video-{video_id}.") and f.suffix == ".mp4":
            return str(f.resolve())
    raise RuntimeError("Downloaded MP4 file not found")

# ---------------- youtube ----------------

def get_latest_video():
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={YOUTUBE_CHANNEL_ID}"
        "&order=date&maxResults=1&type=video"
        f"&key={YOUTUBE_API_KEY}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["items"][0]

# ---------------- download ----------------

def download_video(video_id: str) -> str:
    if is_already_uploaded(video_id):
        print(f"Video {video_id} already uploaded. Skipping.")
        sys.exit(0)

    ydl_opts = {
        "cookies": str(COOKIE_PATH),
        "outtmpl": f"video-{video_id}.%(ext)s",
        "format": "bv*[ext=mp4]+ba/b[ext=mp4]/best",
        "merge_output_format": "mp4",
        "no_cache_dir": True,
        "verbose": True,

        # 🔑 REQUIRED for modern YouTube
        "js_runtimes": ["node"],
        "remote_components": ["ejs:github"],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    final_file = resolve_downloaded_file(video_id)
    mark_as_uploaded(video_id)
    return final_file

# ---------------- facebook ----------------

def upload_to_facebook(file_path: str, title: str, description: str):
    url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos"

    with open(file_path, "rb") as f:
        r = requests.post(
            url,
            files={"source": f},
            data={
                "description": f"{title}\n\n{description}",
                "access_token": FB_PAGE_TOKEN,
            },
            timeout=300,
        )

    if not r.ok:
        raise RuntimeError(f"Facebook upload failed: {r.text}")

    print("Video uploaded successfully:", r.json())

# ---------------- main ----------------

def main():
    video = get_latest_video()
    video_id = video["id"]["videoId"]
    title = video["snippet"]["title"]
    description = video["snippet"]["description"]

    print("Latest video:", video_id)

    file_path = download_video(video_id)
    upload_to_facebook(file_path, title, description)
    delete_video(file_path)

if __name__ == "__main__":
    main()