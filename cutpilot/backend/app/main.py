import json, os, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import DATA, RATIOS
from .pipeline import run_job

app = FastAPI(title="CutPilot")
pool = ThreadPoolExecutor(max_workers=int(os.getenv("JOB_WORKERS", "1")))
JOBS = {}


def save(job):
    (Path(job["dir"]) / "job.json").write_text(json.dumps(job, default=str))


async def store(files, d, prefix):
    out = []
    for i, f in enumerate(files):
        if not f.filename:
            continue
        p = d / "in" / f"{prefix}{i}_{Path(f.filename).name}"
        with open(p, "wb") as o:
            while chunk := await f.read(1 << 20):
                o.write(chunk)
        out.append(str(p))
    return out


@app.post("/api/jobs")
async def create(footage: list[UploadFile] = File(...), reference: list[UploadFile] = File(default=[]),
                 reference_urls: str = Form(""), rights_confirmed: bool = Form(False), prompt: str = Form(""),
                 mode: str = Form("shorts"), ratios: str = Form("9:16"), max_seconds: int = Form(60),
                 look: str = Form("auto"), transition: str = Form("cut"), auto_captions: bool = Form(True),
                 caption_lines: str = Form("")):
    jid = uuid.uuid4().hex[:10]
    d = DATA / "jobs" / jid
    (d / "in").mkdir(parents=True)
    foot = await store(footage, d, "f")
    if not foot:
        raise HTTPException(400, "Upload at least one video or photo.")
    job = dict(id=jid, dir=str(d), status="queued", progress=0, message="Queued", footage=foot,
               reference=await store(reference, d, "r"), reference_urls=[u.strip() for u in reference_urls.splitlines() if u.strip()],
               rights_confirmed=rights_confirmed, prompt=prompt, mode="long" if mode == "long" else "shorts",
               ratios=[r for r in ratios.split(",") if r in RATIOS] or ["9:16"], max_seconds=max(5, min(300, max_seconds)),
               look=look, transition=transition if transition in ("cut", "fade") else "cut", auto_captions=auto_captions,
               caption_lines=[s.strip() for s in caption_lines.splitlines() if s.strip()], outputs={}, plan=None)
    JOBS[jid] = job
    save(job)
    pool.submit(run_job, job, save)
    return {"id": jid}


def get_job(jid):
    job = JOBS.get(jid)
    if not job:
        p = DATA / "jobs" / jid / "job.json"
        if not p.exists():
            raise HTTPException(404, "Unknown job")
        job = json.loads(p.read_text())
    return job


@app.get("/api/jobs/{jid}")
def status(jid: str):
    j = get_job(jid)
    return {k: j.get(k) for k in ("id", "status", "progress", "message", "plan", "outputs")}


@app.get("/api/jobs/{jid}/file/{ratio}")
def file(jid: str, ratio: str):
    j = get_job(jid)
    name = j["outputs"].get(ratio.replace("x", ":"))
    if not name:
        raise HTTPException(404, "Not ready")
    return FileResponse(Path(j["dir"]) / name, media_type="video/mp4", filename=f"cutpilot-{ratio}.mp4")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
