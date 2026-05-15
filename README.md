# SPPU Result Viewer

A frontend tool to check Savitribai Phule Pune University exam results — fetched live from the SPPU online portal.

## Features

- Browse courses by session with search, sort, and category filters
- View result PDFs (enter seat number, mother's name, captcha)
- Revaluation result lookup
- Dark mode, responsive design

## Usage

1. Open the page — courses load automatically
2. Select a session from the dropdown
3. Find your course by searching or filtering
4. Tap a course card, fill in your seat number and mother's name
5. Enter the captcha (loaded from SPPU) and submit
6. Your result opens in a new tab

## Run Locally

```bash
python3 server.py
# → http://localhost:8080
```

Or serve `index.html` as static files. When no backend is available, the embedded course data is used.

## Deploy

| Method | File | Notes |
|--------|------|-------|
| Static (GitHub Pages, etc.) | `index.html` | Uses embedded fallback data |
| Cloudflare Worker | `worker.js` | Full proxy with live SPPU data |
| Python server | `server.py` | Proxy for local/self-hosted |

Python API endpoints (`/api/sessions`, `/api/courses`, `/api/captcha`, `/api/result`, `/api/reval`) double as Vercel serverless functions under `api/`.

## Disclaimer

This project is **not affiliated with or endorsed by Savitribai Phule Pune University**. Results shown are provisional — always verify with the official university marksheet. No personal data is stored or sent to third parties.
