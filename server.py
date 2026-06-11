"""
YT Clip Downloader — Render.com Webhook Server
================================================
Deploy this on Render.com (free tier) as a Web Service.
Make.com sends a POST request here with a video URL.
This server downloads it via yt-dlp and uploads to Google Drive.

Setup steps at the bottom of this file.
"""

import os
import subprocess
import tempfile
import json
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)

# ── Config (set these as Environment Variables in Render dashboard) ──────────
WEBHOOK_SECRET  = os.environ.get("WEBHOOK_SECRET", "change-this-secret")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID", "")        # Google Drive folder ID
GDRIVE_CREDS    = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON", "") # Full JSON as string


# ── Google Drive client ──────────────────────────────────────────────────────
def get_drive_service():
    creds_dict = json.loads(GDRIVE_CREDS)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=creds)


def upload_to_drive(file_path, filename, niche="general"):
    service = get_drive_service()

    # Find or create niche subfolder
    query = (
        f"name='{niche}' and "
        f"'{GDRIVE_FOLDER_ID}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        "trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    folders = results.get("files", [])

    if folders:
        folder_id = folders[0]["id"]
    else:
        folder_meta = {
            "name": niche,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [GDRIVE_FOLDER_ID]
        }
        folder = service.files().create(body=folder_meta, fields="id").execute()
        folder_id = folder["id"]

    # Upload the file
    file_meta = {"name": filename, "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    uploaded = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id,webViewLink"
    ).execute()

    return uploaded.get("webViewLink", "")


# ── Download with yt-dlp ─────────────────────────────────────────────────────
def download_clip(url, output_dir):
    """
    Downloads a clip to output_dir, returns the file path and title.
    Limits to 720p max to keep file sizes reasonable.
    """
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "--output", output_template,
        "--no-playlist",
        "--print", "%(title)s",         # prints title to stdout
        "--no-warnings",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr}")

    title = result.stdout.strip().split("\n")[0]

    # Find the downloaded file
    files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    if not files:
        raise RuntimeError("No mp4 file found after download")

    file_path = os.path.join(output_dir, files[0])
    return file_path, title


# ── Webhook endpoint ─────────────────────────────────────────────────────────
@app.route("/download", methods=["POST"])
def handle_download():
    """
    Expected JSON payload from Make.com:
    {
        "secret":  "your-webhook-secret",
        "url":     "https://www.youtube.com/watch?v=...",
        "niche":   "sports",          (optional, defaults to "general")
        "source":  "ESPN Highlights"  (optional, for Airtable logging)
    }

    Returns:
    {
        "status":     "ok",
        "title":      "Video title here",
        "drive_link": "https://drive.google.com/...",
        "niche":      "sports"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    # Auth check
    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    url   = data.get("url", "").strip()
    niche = data.get("niche", "general").strip()

    if not url:
        return jsonify({"error": "Missing url field"}), 400

    # Download to a temp directory, then upload to Drive
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            file_path, title = download_clip(url, tmpdir)
            filename = os.path.basename(file_path)
            drive_link = upload_to_drive(file_path, filename, niche)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            return jsonify({"error": f"Unexpected: {str(e)}"}), 500

    return jsonify({
        "status":     "ok",
        "title":      title,
        "drive_link": drive_link,
        "niche":      niche
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP GUIDE — READ THIS BEFORE DEPLOYING
# ══════════════════════════════════════════════════════════════════════════════
#
#  STEP 1 — Create a Google Cloud Service Account
#  ────────────────────────────────────────────────
#  1. Go to console.cloud.google.com → New Project → "ytclip-automation"
#  2. APIs & Services → Enable: "Google Drive API"
#  3. Credentials → Create Credentials → Service Account
#     Name: ytclip-server   Role: Editor
#  4. Click the service account → Keys → Add Key → JSON
#     Save the downloaded JSON file
#  5. In Google Drive, create a folder called "YT Clips"
#     Right-click → Share → paste the service account email (ends in @...iam.gserviceaccount.com)
#     Give it Editor access
#  6. Copy the folder ID from the URL:
#     drive.google.com/drive/folders/THIS_PART_IS_THE_ID
#
#  STEP 2 — Deploy to Render.com
#  ────────────────────────────────────────────────
#  1. Push this project to a GitHub repo (needs server.py, requirements.txt, render.yaml)
#  2. Go to render.com → New → Web Service → connect your GitHub repo
#  3. Runtime: Python 3  |  Build Command: pip install -r requirements.txt && apt-get install -y yt-dlp
#     (or see render.yaml which handles this automatically)
#  4. Start Command: python server.py
#  5. Add Environment Variables in Render dashboard:
#       WEBHOOK_SECRET            → make up a strong random string (e.g. "sk-ytclip-abc123xyz")
#       GDRIVE_FOLDER_ID          → the folder ID from Step 1
#       GDRIVE_SERVICE_ACCOUNT_JSON → paste the ENTIRE contents of the JSON key file
#
#  STEP 3 — Test it
#  ────────────────────────────────────────────────
#  Once deployed, your URL will be: https://your-app-name.onrender.com
#  Test with curl:
#
#  curl -X POST https://your-app-name.onrender.com/download \
#    -H "Content-Type: application/json" \
#    -d '{"secret":"your-secret","url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","niche":"test"}'
#
#  You should get back a JSON response with the Drive link,
#  and the file will appear in your Google Drive YT Clips folder.
#
# ══════════════════════════════════════════════════════════════════════════════
