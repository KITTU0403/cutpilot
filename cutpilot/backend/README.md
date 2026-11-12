# CutPilot backend

Raw footage + reference video + prompt in, finished edited videos out (every aspect ratio, max 5 min).

## Pipeline
1. **Probe + proxies**: ffprobe, 480p proxies for fast analysis (handles phone rotation).
2. **Transcribe**: faster-whisper, word timestamps, auto language (Telugu, Hindi, English...).
3. **Footage analysis**: per-second sharpness, motion, brightness, faces, audio energy, speech density, scored into "best moments"; contact sheets for vision.
4. **Reference analysis**: PySceneDetect shot lengths and cut rate, color mood, motion, contact sheet.
5. **AI director**: Claude gets prompt, transcript, scores, contact sheets and reference style, and returns the edit plan through a forced tool call (`submit_plan`). Cuts are snapped to word boundaries and the 300 s cap is enforced. Without `ANTHROPIC_API_KEY` a local fallback planner is used.
6. **Smart reframe**: face tracking per segment becomes a smoothed ffmpeg `crop` expression that follows the subject, then scales to each ratio.
7. **Render**: per segment (look, punch-in zoom, fades), concat, burned-in word-highlight captions (ASS), loudness normalization (-14 LUFS). Ratios render in parallel.

## Run
```bash
export ANTHROPIC_API_KEY=sk-ant-...        # AI director
pip install -r requirements.txt            # also needs ffmpeg on PATH
uvicorn app.main:app --host 0.0.0.0 --port 8000
# or: docker build -t cutpilot . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY -v $PWD/data:/data cutpilot
```
Open http://localhost:8000. Offline check (no Whisper or Claude needed): `python -m tests.smoke_render`.

## Settings (env)
`CLAUDE_MODEL` (default claude-sonnet-5-5), `WHISPER_MODEL` (small; use large-v3 on GPU for best Telugu/Hindi), `JOB_WORKERS`, `RENDER_WORKERS`, `DATA_DIR`, `ALLOW_URL_REFERENCES=1` (enables yt-dlp for reference links; only with rights, mind platform terms).

## API
`POST /api/jobs` (multipart: footage[], reference[], reference_urls, prompt, mode, ratios, max_seconds, look, transition, auto_captions, caption_lines) returns `{id}`.
`GET /api/jobs/{id}` returns status, progress, plan, outputs. `GET /api/jobs/{id}/file/9x16` returns the MP4.

## Before real users
- Jobs run in an in-process queue with JSON state on disk. For scale use Redis + Celery/RQ workers, S3/R2 storage, GPU workers for Whisper.
- Face detector is OpenCV Haar (frontal faces). For best results swap `face_detector()` in `app/reframe.py` for YuNet or MediaPipe.
- Add auth, upload size limits, per-user credits, cleanup of old jobs, and royalty-free music (ducking) as next features.
