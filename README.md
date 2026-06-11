# YT Clip Auto-Downloader System

Automatic pipeline: YouTube RSS feeds → download via yt-dlp → Google Drive → Airtable production dashboard.

---

## Files in this project

| File                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `server.py`         | Flask webhook server — deploy this to Render.com     |
| `requirements.txt`  | Python dependencies for Render                       |
| `render.yaml`       | Render build config — installs yt-dlp automatically  |
| `make-blueprint.json` | Make.com scenario — import this to set up automation |
| `airtable-setup.md` | Exact fields, views and workflow for your dashboard  |

---

## Quick-start order

### Phase 1 — Google Drive (15 min)
1. Create Google Cloud project at console.cloud.google.com
2. Enable Google Drive API
3. Create a Service Account → download JSON key
4. In Google Drive: create "YT Clips" folder, share with service account email
5. Copy the folder ID from the URL

### Phase 2 — Deploy server (20 min)
1. Push this repo to GitHub
2. Go to render.com → New Web Service → connect repo
3. Add 3 environment variables:
   - `WEBHOOK_SECRET` — any strong random string
   - `GDRIVE_FOLDER_ID` — from Phase 1
   - `GDRIVE_SERVICE_ACCOUNT_JSON` — entire contents of the JSON key file
4. Deploy. Wait ~3 min for first build.
5. Test: `curl https://your-app.onrender.com/health` → should return `{"status":"running"}`

### Phase 3 — Airtable (10 min)
1. Create base "YT Clip System" with table "Clips"
2. Add all fields from airtable-setup.md
3. Create the 4 views
4. Get your Base ID from the URL

### Phase 4 — Make.com (20 min)
1. Go to make.com → Scenarios → Import Blueprint → upload make-blueprint.json
2. Fill in all REPLACE_WITH_... placeholders
3. Add RSS feed URLs (see make-blueprint.json for YouTube channel RSS format)
4. Connect your Airtable account
5. Turn the scenario ON
6. Click "Run once" to test → check Drive and Airtable for results

---

## Adding more source channels

In Make.com, right-click the RSS module → Clone. Change the URL to a new channel RSS feed.
All other modules connect automatically.

## Changing the download quality

In server.py, find the `--format` line in `download_clip()`.
- 720p (default): `bestvideo[height<=720]...`
- 1080p: change 720 to 1080
- Audio only: `bestaudio[ext=m4a]`

## Total running cost

| Service       | Cost          |
|---------------|---------------|
| Render.com    | Free          |
| Make.com      | Free (1K ops) |
| Google Drive  | Free (15GB)   |
| Airtable      | Free (1.2K rows) |
| **Total**     | **$0/month**  |

Upgrade Make.com to Core ($9/mo) if you're running more than ~30 downloads per month.
