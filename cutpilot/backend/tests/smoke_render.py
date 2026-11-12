"""Offline smoke test (no Whisper / Claude needed): python -m tests.smoke_render"""
import tempfile
from pathlib import Path
from app.media import run, probe, make_proxy, audio_energy
from app.analyze import sample_clip, score_samples, contact_sheet
from app.reframe import track_faces
from app.render import render_segment, assemble
from app.captions import build_ass
from app.planner import fallback

tmp = Path(tempfile.mkdtemp())
src = tmp / "src.mp4"
run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=10",
     "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(src)])
info = probe(src)
clip = dict(name="src.mp4", path=str(src), kind="video", proxy=str(tmp / "p.mp4"), **info)
make_proxy(src, clip["proxy"])
m, th = sample_clip(clip["proxy"], info["duration"], 1.0)
clip["moments"] = score_samples(m, audio_energy(src), [], 1.0)
clip["words"] = [dict(w=w, s=2 + i * .4, e=2.35 + i * .4) for i, w in enumerate("this is a test of word captions".split())]
assert contact_sheet(th), "contact sheet failed"
plan = fallback(dict(mode="shorts"), [clip], [], 6.0)
print("plan:", plan["segments"])
for ratio, (W, H) in {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}.items():
    files = []
    for i, s in enumerate(plan["segments"]):
        f = tmp / f"{ratio.replace(':', 'x')}_{i}.mp4"
        render_segment(clip, s, track_faces(clip["proxy"], s["start"], s["end"]), W, H, "warm", True, f)
        files.append(f)
    out = tmp / f"out_{ratio.replace(':', 'x')}.mp4"
    assemble(files, tmp, build_ass(plan["segments"], [clip], W, H, "shorts"), out)
    p = probe(out)
    print(ratio, f"{p['width']}x{p['height']}", f"{p['duration']:.1f}s", "audio" if p["has_audio"] else "NO AUDIO")
    assert (p["width"], p["height"]) == (W, H) and p["has_audio"]
print("SMOKE TEST OK")
