import os, traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .config import IMAGE_EXT, RATIOS
from .media import probe, make_proxy, audio_energy, run
from .analyze import sample_clip, score_samples, contact_sheet, reference_style
from .transcribe import transcribe
from .reframe import track_faces
from .captions import build_ass
from .render import render_segment, assemble
from .planner import make_plan


def fetch_reference(url, work):
    import yt_dlp
    out = str(work / "ref_dl.%(ext)s")
    opts = {"outtmpl": out, "format": "mp4[height<=720]/best[height<=720]", "quiet": True, "noplaylist": True,
            "match_filter": lambda i, **k: None if (i.get("duration") or 0) <= 300 else "too long"}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
        return y.prepare_filename(info)


def load_clips(paths, work):
    clips = []
    for i, p in enumerate(paths):
        p = Path(p)
        img = p.suffix.lower() in IMAGE_EXT
        info = probe(p)
        c = dict(name=p.name.split("_", 1)[-1], path=str(p), kind="image" if img else "video", **info)
        if img:
            c.update(duration=3.0, has_audio=False)
        else:
            c["proxy"] = str(work / f"proxy_{i}.mp4")
            make_proxy(p, c["proxy"])
        clips.append(c)
    return clips


def run_job(job, save):
    def up(p, m):
        job.update(progress=p, message=m, status="running")
        save(job)
    try:
        d = Path(job["dir"])
        work = d / "work"
        work.mkdir(exist_ok=True)
        up(3, "Reading footage and building proxies")
        clips = load_clips(job["footage"], work)
        vids = [c for c in clips if c["kind"] == "video"]
        for n, c in enumerate(vids):
            base = 5 + 45 * n / max(1, len(vids))
            if c["has_audio"]:
                up(base, f"Transcribing {c['name']}")
                c["transcript"], c["words"], c["lang"] = transcribe(c["path"])
                c["energy"] = audio_energy(c["path"])
            up(base + 20 / max(1, len(vids)), f"Analyzing shots in {c['name']}")
            step = max(1.0, c["duration"] / 120)
            m, thumbs = sample_clip(c["proxy"], c["duration"], step)
            c["moments"] = score_samples(m, c.get("energy", []), c.get("words", []), step)
            c["sheet"] = contact_sheet(thumbs)
        refs, paths, notes = [], list(job["reference"]), []
        if job["reference_urls"]:
            if os.getenv("ALLOW_URL_REFERENCES") == "1" and job["rights_confirmed"]:
                for u in job["reference_urls"][:2]:
                    try:
                        paths.append(fetch_reference(u, work))
                    except Exception as e:
                        notes.append(f"Could not fetch {u}: {e}")
            else:
                notes.append("Reference links skipped: enable ALLOW_URL_REFERENCES=1 and confirm you have the rights, or upload the file.")
        for k, p in enumerate(paths[:2]):
            up(52 + k * 4, "Analyzing reference style")
            prox = work / f"ref_{k}.mp4"
            make_proxy(p, prox)
            refs.append(reference_style(prox, probe(p)["duration"]))
        up(62, "AI director is planning the edit")
        plan = make_plan(job, clips, refs)
        plan["notes"] = (plan.get("notes", "") + " " + " ".join(notes)).strip()
        job["plan"] = plan
        segs = plan["segments"]
        up(66, "Tracking faces for smart reframing")
        tracks = [track_faces(clips[s["clip"]]["proxy"], s["start"], s["end"]) if clips[s["clip"]]["kind"] == "video" else None for s in segs]

        def render_ratio(r):
            W, H = RATIOS[r]
            wd = work / r.replace(":", "x")
            wd.mkdir(exist_ok=True)
            files = []
            for i, s in enumerate(segs):
                f = wd / f"seg{i:03d}.mp4"
                render_segment(clips[s["clip"]], s, tracks[i], W, H, plan["look"], plan["transition"] == "fade", f)
                files.append(f)
            ass = build_ass(segs, clips, W, H, job["mode"], job["auto_captions"])
            out = d / f"out_{r.replace(':', 'x')}.mp4"
            assemble(files, wd, ass, out)
            return r, out.name
        with ThreadPoolExecutor(max_workers=int(os.getenv("RENDER_WORKERS", "2"))) as ex:
            for n, (r, name) in enumerate(ex.map(render_ratio, job["ratios"])):
                job["outputs"][r] = name
                up(70 + 29 * (n + 1) / len(job["ratios"]), f"Rendered {r}")
        job.update(status="done", progress=100, message="Done")
    except Exception as e:
        traceback.print_exc()
        job.update(status="error", message=str(e)[:400])
    save(job)
