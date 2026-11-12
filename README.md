# CutPilot

AI video editor: give it raw footage, reference videos and a prompt, get a finished edit in every aspect ratio (9:16, 16:9, 1:1, 4:5, 4:3, 21:9), up to 5 minutes. Built for Reels/Shorts creators and long-form editors.

Two versions live in this repo:

| | Browser version (`docs/`) | Full server version (`backend/`) |
|---|---|---|
| Setup | None. Static page | Python, FFmpeg or Docker |
| Where it runs | Your browser, files never leave your device | Your server |
| Speech captions (Whisper) | No (type caption lines) | Yes, word-highlight captions, Telugu/Hindi/English |
| Face-tracking reframe | No (center crop + zoom) | Yes |
| Prompt understanding | On-device rules (AI director when opened inside Claude) | Claude via `ANTHROPIC_API_KEY`, local fallback without a key |
| Render speed | Real time | Fast (FFmpeg) |

## Browser version on GitHub Pages
1. Repo **Settings > Pages**.
2. Source: **Deploy from a branch**, branch `main`, folder `/docs`, then Save.
3. Your site is live at `https://<your-username>.github.io/<repo-name>/`.

## Server version
```bash
docker compose up --build          # open http://localhost:8000
# optional: ANTHROPIC_API_KEY=sk-ant-... docker compose up --build
```
Without Docker: see `backend/README.md`. To host it online, deploy `backend/Dockerfile` on any Docker host (Render, Railway, Fly.io, RunPod, a VPS). Use a GPU host and `WHISPER_MODEL=large-v3` for best Telugu/Hindi accuracy.

## Tests
`cd backend && python -m tests.smoke_render && python -m tests.smoke_pipeline` (needs FFmpeg, numpy, opencv).

## Notes
- Reference links: downloading is off by default. Upload the file, or set `ALLOW_URL_REFERENCES=1` only if you have the rights and the platform allows it.
- Add auth, upload limits and job cleanup before opening it to the public.

MIT License.
