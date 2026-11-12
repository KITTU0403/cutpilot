import numpy as np


def _norm(a):
    a = np.asarray(a, dtype=float)
    return np.clip(a / (np.percentile(a, 95) + 1e-9), 0, 1) if len(a) else a


def sample_clip(proxy, dur, step):
    """Sample frames: sharpness, motion, brightness, faces. Also returns thumbnails for contact sheets."""
    import cv2
    cap = cv2.VideoCapture(str(proxy))
    from .reframe import face_detector
    det = face_detector()
    out, thumbs, prev, t = [], [], None, step / 2
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            break
        h, w = f.shape[:2]
        g = cv2.cvtColor(cv2.resize(f, (320, max(2, int(320 * h / w)))), cv2.COLOR_BGR2GRAY)
        gf = g.astype(np.float32)
        out.append(dict(t=t, sharp=float(cv2.Laplacian(g, cv2.CV_64F).var()), luma=float(g.mean() / 255),
                        motion=float(np.abs(gf - prev).mean() / 255) if prev is not None else 0.0,
                        faces=int(len(det(g)))))
        thumbs.append((t, cv2.resize(f, (256, 144))))
        prev, t = gf, t + step
    cap.release()
    return out, thumbs


def score_samples(metrics, energy, words, step):
    if not metrics:
        return []
    sh, mo = _norm([m["sharp"] for m in metrics]), _norm([m["motion"] for m in metrics])
    emax = max(energy) if energy else 1
    sp = _norm([sum(1 for w in words if abs(w["s"] - m["t"]) <= step / 2) for m in metrics]) if words else np.zeros(len(metrics))
    for i, m in enumerate(metrics):
        en = energy[min(len(energy) - 1, int(m["t"] / 0.5))] / emax if energy else 0.5
        ok = 0.0 if (m["luma"] < 0.07 or m["luma"] > 0.96) else 1.0
        m["score"] = float(ok * (0.3 * sh[i] + 0.2 * mo[i] + 0.2 * en + 0.15 * (m["faces"] > 0) + 0.15 * sp[i]))
    return metrics


def contact_sheet(thumbs, n=12, cols=4):
    import cv2
    if not thumbs:
        return None
    idx = np.linspace(0, len(thumbs) - 1, min(n, len(thumbs))).astype(int)
    tiles = []
    for i in idx:
        t, im = thumbs[i]
        im = im.copy()
        cv2.rectangle(im, (0, 0), (70, 20), (0, 0, 0), -1)
        cv2.putText(im, f"{t:.1f}s", (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(im)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)]
    return cv2.imencode(".jpg", np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()


def reference_style(proxy, dur):
    """Shot lengths, cut rate, color mood and motion of a reference video (first 120 s)."""
    import cv2
    from scenedetect import detect, ContentDetector
    d = min(dur, 120)
    scenes = detect(str(proxy), ContentDetector(threshold=27), end_time=d)
    lens = [b.get_seconds() - a.get_seconds() for a, b in scenes] or [d]
    metrics, thumbs = sample_clip(proxy, d, max(1.0, d / 40))
    sat = [cv2.cvtColor(im, cv2.COLOR_BGR2HSV)[..., 1].mean() / 255 for _, im in thumbs] or [0.2]
    warm = [(im[..., 2].astype(float).mean() - im[..., 0].astype(float).mean()) / 255 for _, im in thumbs] or [0.0]
    s, w = float(np.mean(sat)), float(np.mean(warm))
    look = "bw" if s < 0.06 else "warm" if w > 0.08 else "cool" if w < -0.04 else "vivid" if s > 0.3 else "none"
    return dict(avg_shot_len=float(np.mean(lens)), median_shot_len=float(np.median(lens)), cuts=len(lens) - 1,
                cuts_per_minute=float((len(lens) - 1) / d * 60), motion=float(np.mean([m["motion"] for m in metrics] or [0])),
                look=look, duration=float(dur), sheet=contact_sheet(thumbs, 8))
