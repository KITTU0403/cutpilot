import base64, json, os, re
from .config import CLAUDE_MODEL

TOOL = {
    "name": "submit_plan",
    "description": "Submit the final edit plan.",
    "input_schema": {"type": "object", "properties": {
        "look": {"type": "string", "enum": ["none", "warm", "cool", "bw", "vivid", "cinematic"]},
        "transition": {"type": "string", "enum": ["cut", "fade"]},
        "notes": {"type": "string", "description": "One or two sentences on the editing approach."},
        "segments": {"type": "array", "items": {"type": "object", "properties": {
            "clip": {"type": "integer"}, "start": {"type": "number"}, "end": {"type": "number"},
            "zoom": {"type": "string", "enum": ["in", "none"]},
            "caption": {"type": "string", "description": "Only when the user asked for text overlays."}},
            "required": ["clip", "start", "end"]}}},
        "required": ["segments"]},
}


def parse_target(prompt, cap):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(minutes?|mins?|seconds?|secs?|s)\b", prompt or "", re.I)
    if not m:
        return None
    v = float(m.group(1)) * (60 if m.group(2).lower().startswith("m") else 1)
    return min(v, cap)


def compact_transcript(segs, limit=7000):
    lines = [f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segs]
    txt = "\n".join(lines)
    if len(txt) > limit:
        k = len(txt) // limit + 1
        txt = "\n".join(lines[::k]) + "\n(transcript thinned)"
    return txt


def _img(b):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(b).decode()}}


def ask_claude(job, clips, refs, target, mx):
    import anthropic
    c = [{"type": "text", "text": (
        "You are a senior video editor. Plan the edit by calling submit_plan.\n"
        f"User prompt: {job['prompt'] or '(none)'}\n"
        f"Mode: {'short-form reel: strongest hook in the first 2 seconds, fast cuts, cut dead air and filler words' if job['mode'] == 'shorts' else 'long-form: chronological story with clear structure, calmer pacing, trim pauses and filler'}\n"
        f"Hard maximum {mx:.0f}s total. Target about {target:.0f}s.\n"
        f"User wants text overlays: {'yes, use their lines' if job['caption_lines'] else 'no (captions are generated automatically from speech)'}. Lines: {json.dumps(job['caption_lines'])}")}]
    if refs:
        c.append({"type": "text", "text": "Reference style to imitate (pace, look, rhythm): " + json.dumps(
            [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "sheet"} for r in refs])})
        c += [_img(r["sheet"]) for r in refs[:1] if r.get("sheet")]
    for i, k in enumerate(clips):
        best = sorted(k.get("moments", []), key=lambda m: -m["score"])[:8]
        c.append({"type": "text", "text": (
            f"--- Clip {i}: {k['name']} ({k['kind']}), {k['duration']:.1f}s, audio={k['has_audio']}, language={k.get('lang', '-')}\n"
            f"Best moments by motion/sharpness/audio/faces (t:score): {', '.join(f'{m['t']:.1f}:{m['score']:.2f}' for m in best)}\n"
            f"Transcript:\n{compact_transcript(k['transcript']) if k.get('transcript') else '(none)'}\n"
            "Contact sheet frames below are labeled with timestamps.")})
        if k.get("sheet"):
            c.append(_img(k["sheet"]))
    c.append({"type": "text", "text": (
        "Rules: choose the best moments; skip dark, blurry, dull or repeated parts; start and end segments on sentence or word "
        "boundaries when there is speech; each segment lies inside its clip; no overlapping reuse; total never above the maximum; "
        "match the reference pace if given; use zoom 'in' on emphasis moments only.")})
    r = anthropic.Anthropic().messages.create(model=CLAUDE_MODEL, max_tokens=4000, tools=[TOOL],
                                              tool_choice={"type": "tool", "name": "submit_plan"},
                                              messages=[{"role": "user", "content": c}])
    return next(b.input for b in r.content if b.type == "tool_use")


def _snap(t, words, key):
    near = [w[key] for w in words if abs(w[key] - t) <= 0.35]
    return min(near, key=lambda x: abs(x - t)) if near else t


def clean(raw, clips, mx):
    segs, tot = [], 0.0
    for s in raw.get("segments", []):
        i = s.get("clip")
        if not isinstance(i, int) or not 0 <= i < len(clips):
            continue
        k = clips[i]
        if k["kind"] == "image":
            a, b = 0.0, min(3.0, max(1.5, float(s.get("end", 0)) - float(s.get("start", 0)) or 2.5))
        else:
            a = max(0.0, float(s.get("start", 0)))
            b = min(k["duration"], float(s.get("end", 0)))
            a, b = _snap(a, k.get("words", []), "s"), _snap(b, k.get("words", []), "e")
        b = min(b, a + (mx - tot))
        if b - a < 0.6:
            continue
        tot += b - a
        segs.append(dict(clip=i, start=round(a, 2), end=round(b, 2), zoom="in" if s.get("zoom") == "in" else "none",
                         caption=str(s.get("caption") or "")))
        if tot >= mx - 0.05:
            break
    return dict(segments=segs, look=raw.get("look"), transition=raw.get("transition"), notes=raw.get("notes", "")) if segs else None


def fallback(job, clips, refs, target):
    pace = (sum(r["avg_shot_len"] for r in refs) / len(refs)) if refs else (1.8 if job["mode"] == "shorts" else 4.0)
    pace = min(max(pace, 0.8), 8.0)
    n = max(1, round(target / pace))
    L = target / n
    cands = []
    for i, k in enumerate(clips):
        if k["kind"] == "image":
            cands.append((0.5, i, 0.0, min(3.0, L)))
        for m in k.get("moments", []):
            l = min(L, k["duration"])
            cands.append((m["score"], i, max(0.0, min(m["t"] - l / 2, k["duration"] - l)), l))
    cands.sort(key=lambda x: -x[0])
    pick = []
    for sc, i, a, l in cands:
        if len(pick) >= n:
            break
        if any(p[1] == i and abs(p[2] - a) < max(p[3], l) for p in pick):
            continue
        pick.append((sc, i, a, l))
    if not pick:
        return None
    order = lambda p: (p[1], p[2])
    pick = sorted(pick, key=order) if job["mode"] == "long" else [pick[0]] + sorted(pick[1:], key=order)
    segs = [dict(clip=i, start=round(a, 2), end=round(a + l, 2), zoom="in" if j % 2 == 0 else "none", caption="")
            for j, (sc, i, a, l) in enumerate(pick)]
    return clean(dict(segments=segs, notes="Planned from motion, sharpness, audio energy and faces (no AI key set)."), clips, target + 0.5)


def make_plan(job, clips, refs):
    mx = float(min(300, job["max_seconds"]))
    total = sum(k["duration"] if k["kind"] == "video" else 3 for k in clips)
    target = parse_target(job["prompt"], mx) or (min(45, total, mx) if job["mode"] == "shorts" else min(total, mx))
    target = max(2.0, min(target, mx, total))
    plan, note = None, ""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            plan = clean(ask_claude(job, clips, refs, target, mx), clips, mx)
            if plan:
                plan["source"] = "claude"
        except Exception as e:
            note = f"Claude planning failed ({type(e).__name__}); used fallback planner."
    if not plan:
        plan = fallback(job, clips, refs, target)
        if not plan:
            raise RuntimeError("No usable moments found in the footage.")
        plan["source"] = "fallback"
        plan["notes"] = (plan.get("notes", "") + " " + note).strip()
    if job["look"] != "auto":
        plan["look"] = job["look"]
    plan["look"] = plan.get("look") or (refs[0]["look"] if refs else "none")
    plan["transition"] = job["transition"] if job["transition"] else (plan.get("transition") or "cut")
    plan["total"] = round(sum(s["end"] - s["start"] for s in plan["segments"]), 2)
    return plan
