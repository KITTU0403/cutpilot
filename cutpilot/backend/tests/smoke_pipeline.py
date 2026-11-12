"""End-to-end pipeline test with Whisper stubbed and no API key (fallback planner): python -m tests.smoke_pipeline"""
import os, tempfile
os.environ.pop("ANTHROPIC_API_KEY", None)
from pathlib import Path
from app import pipeline
from app.media import run, probe

tmp = Path(tempfile.mkdtemp())
(tmp / "in").mkdir()
src = tmp / "in" / "f0_clip.mp4"
run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20",
     "-f", "lavfi", "-i", "sine=frequency=330:duration=20", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)])
words = [dict(w=w, s=1 + i * .45, e=1.4 + i * .45) for i, w in enumerate("hello this is a pipeline test with fake speech".split() * 4)]
pipeline.transcribe = lambda p: ([dict(start=1, end=19, text="fake")], words, "en")
job = dict(id="t", dir=str(tmp), status="queued", progress=0, message="", footage=[str(src)], reference=[], reference_urls=[],
           rights_confirmed=False, prompt="20 sec energetic reel", mode="shorts", ratios=["9:16", "16:9"], max_seconds=30,
           look="auto", transition="cut", auto_captions=True, caption_lines=[], outputs={}, plan=None)
pipeline.run_job(job, lambda j: None)
print(job["status"], job["message"])
assert job["status"] == "done", job["message"]
for r, name in job["outputs"].items():
    p = probe(tmp / name)
    print(r, p["width"], "x", p["height"], round(p["duration"], 1), "s")
print("PIPELINE TEST OK, plan source:", job["plan"]["source"], "segments:", len(job["plan"]["segments"]))
