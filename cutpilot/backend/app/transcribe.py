from .config import WHISPER_MODEL

_model = None


def transcribe(path):
    """Word-level transcript with timestamps. Language is auto-detected (Telugu, Hindi, English...)."""
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="auto")
    segs, info = _model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    out, words = [], []
    for s in segs:
        out.append(dict(start=float(s.start), end=float(s.end), text=s.text.strip()))
        words += [dict(w=w.word.strip(), s=float(w.start), e=float(w.end)) for w in (s.words or [])]
    return out, words, info.language
