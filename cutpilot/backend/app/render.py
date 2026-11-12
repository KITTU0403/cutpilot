from pathlib import Path
from .media import run

LOOKS = {
    "none": "", "warm": "eq=saturation=1.15:contrast=1.04,colorbalance=rs=0.06:bs=-0.06",
    "cool": "colorbalance=rs=-0.05:bs=0.07,eq=saturation=1.05", "bw": "hue=s=0,eq=contrast=1.15",
    "vivid": "eq=saturation=1.45:contrast=1.08", "cinematic": "eq=contrast=1.1:saturation=0.9,colorbalance=rs=0.05:bs=-0.04",
}


def crop_size(sw, sh, ar, zoom):
    cw, ch = (sh * ar, sh) if sw / sh > ar else (sw, sw / ar)
    return max(2, int(cw / zoom) // 2 * 2), max(2, int(ch / zoom) // 2 * 2)


def lin_expr(pts):
    """Piecewise-linear ffmpeg expression in t from [(t, value)]."""
    if len(pts) > 40:
        pts = pts[:: len(pts) // 40 + 1] + [pts[-1]]
    e = f"{pts[-1][1]:.1f}"
    for (t0, v0), (t1, v1) in reversed(list(zip(pts[:-1], pts[1:]))):
        k = (v1 - v0) / max(t1 - t0, 1e-3)
        e = f"if(lt(t,{t1:.3f}),{v0:.1f}+({k:.3f})*(t-{t0:.3f}),{e})"
    return e


def render_segment(clip, seg, track, W, H, look, fade, out):
    d, sw, sh = seg["end"] - seg["start"], clip["width"], clip["height"]
    zoom = 1.12 if seg.get("zoom") == "in" else 1.0
    cw, ch = crop_size(sw, sh, W / H, zoom)
    track = track or [(0.0, 0.5, 0.5)]
    clamp = lambda v, hi: min(max(v, 0), hi)
    xe = lin_expr([(t, clamp(cx * sw - cw / 2, sw - cw)) for t, cx, cy in track])
    ye = lin_expr([(t, clamp(cy * sh - ch / 2, sh - ch)) for t, cx, cy in track])
    vf = ["setpts=PTS-STARTPTS", f"crop=w={cw}:h={ch}:x='{xe}':y='{ye}'", f"scale={W}:{H}:flags=lanczos", "setsar=1", "fps=30"]
    if LOOKS.get(look):
        vf.append(LOOKS[look])
    af = ["aresample=48000"]
    if fade:
        f = min(0.2, d / 4)
        vf += [f"fade=t=in:st=0:d={f}", f"fade=t=out:st={max(d - f, 0):.3f}:d={f}"]
        af += [f"afade=t=in:st=0:d={f}", f"afade=t=out:st={max(d - f, 0):.3f}:d={f}"]
    img = clip["kind"] == "image"
    has_a = clip.get("has_audio") and not img
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    cmd += ["-loop", "1", "-framerate", "30", "-i", clip["path"]] if img else ["-ss", f"{seg['start']:.3f}", "-i", clip["path"]]
    if not has_a:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += ["-t", f"{d:.3f}", "-vf", ",".join(vf), "-af", ",".join(af), "-map", "0:v:0", "-map", "0:a:0" if has_a else "1:a:0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", str(out)]
    run(cmd)


def assemble(seg_files, workdir, ass_text, out):
    workdir = Path(workdir)
    (workdir / "list.txt").write_text("".join(f"file '{Path(p).resolve()}'\n" for p in seg_files))
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "concat.mp4"], cwd=workdir)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", "concat.mp4"]
    if ass_text and "Dialogue:" in ass_text:
        (workdir / "captions.ass").write_text(ass_text, encoding="utf-8")
        cmd += ["-vf", "ass=captions.ass", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(Path(out).resolve())]
    run(cmd, cwd=workdir)
