def face_detector():
    """Haar face detector (OpenCV 4.x). Returns a callable gray_image -> [(x, y, w, h)]. Swap in YuNet/MediaPipe for higher quality."""
    import cv2
    try:
        det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        return lambda g: det.detectMultiScale(g, 1.1, 5, minSize=(24, 24))
    except AttributeError:
        return lambda g: []


def track_faces(proxy, t0, t1, step=0.4):
    """Face-follow keypoints [(t_rel, cx, cy)] with normalized centers, smoothed to avoid jitter."""
    import cv2
    cap = cv2.VideoCapture(str(proxy))
    det = face_detector()
    pts, last, t = [], (0.5, 0.5), t0
    while t <= t1 + 1e-6:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, f = cap.read()
        if not ok:
            break
        h, w = f.shape[:2]
        g = cv2.cvtColor(cv2.resize(f, (360, max(2, int(360 * h / w)))), cv2.COLOR_BGR2GRAY)
        fs = det(g)
        if len(fs):
            x, y, fw, fh = max(fs, key=lambda r: r[2] * r[3])
            last = ((x + fw / 2) / g.shape[1], (y + fh / 2) / g.shape[0])
        pts.append((t - t0, last[0], last[1]))
        t += step
    cap.release()
    return smooth(pts)


def smooth(pts, dead=0.04, alpha=0.45):
    if not pts:
        return [(0.0, 0.5, 0.5)]
    out, cx, cy = [], pts[0][1], pts[0][2]
    for t, x, y in pts:
        if abs(x - cx) > dead:
            cx += (x - cx) * alpha
        if abs(y - cy) > dead:
            cy += (y - cy) * alpha
        out.append((t, cx, cy))
    return out
