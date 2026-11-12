import json, subprocess
import numpy as np


def run(cmd, cwd=None):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if p.returncode:
        raise RuntimeError(p.stderr[-2000:])
    return p.stdout


def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot) or 0)
    rot = rot or int(v.get("tags", {}).get("rotate", 0) or 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    dur = float(j["format"].get("duration") or 0)
    return dict(width=w, height=h, duration=dur, has_audio=any(s["codec_type"] == "audio" for s in j["streams"]))


def make_proxy(src, dst):
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", "scale=-2:480,fps=15", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", str(dst)])


def audio_energy(src, win=0.5):
    p = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                       capture_output=True)
    x = np.frombuffer(p.stdout, dtype=np.float32)
    n = int(16000 * win)
    if len(x) < n:
        return []
    x = x[: len(x) // n * n].reshape(-1, n)
    return np.sqrt((x ** 2).mean(axis=1)).tolist()
