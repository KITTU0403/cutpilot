def _ts(t):
    t = max(t, 0.0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _clean(s):
    return s.replace("{", "(").replace("}", ")").replace("\\", "")


def build_ass(segments, clips, W, H, mode, use_words=True):
    """ASS subtitles. Shorts: big word-highlight captions. Long: clean bottom subtitles."""
    sh = mode == "shorts"
    fs, mv = int(min(W, H) * (0.075 if sh else 0.04)), int(H * (0.2 if sh else 0.07))
    prim = "&H0000D4FF" if sh else "&H00FFFFFF"
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\n\n[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
            f"Style: Main,DejaVu Sans,{fs},{prim},&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{max(3, fs // 12)},0,2,60,60,{mv},1\n\n"
            "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    lines, t_out = [], 0.0
    for s in segments:
        a, b, dur = s["start"], s["end"], s["end"] - s["start"]
        words = [w for w in clips[s["clip"]].get("words", []) if w["s"] >= a - 0.05 and w["e"] <= b + 0.05] if use_words else []
        if words:
            chunk, maxw = [], 3 if sh else 9
            groups = []
            for i, w in enumerate(words):
                chunk.append(w)
                gap = words[i + 1]["s"] - w["e"] if i + 1 < len(words) else 9
                if len(chunk) >= maxw or gap > 0.6 or w["w"][-1:] in ".?!।":
                    groups.append(chunk)
                    chunk = []
            if chunk:
                groups.append(chunk)
            for g in groups:
                st, en = t_out + g[0]["s"] - a, t_out + g[-1]["e"] - a
                if sh:
                    txt = "".join("{\\kf%d}%s " % (max(1, int((w["e"] - w["s"]) * 100)), _clean(w["w"]).upper()) for w in g)
                else:
                    txt = _clean(" ".join(w["w"] for w in g))
                lines.append(f"Dialogue: 0,{_ts(st)},{_ts(en)},Main,,0,0,0,,{txt.strip()}")
        elif s.get("caption"):
            txt = _clean(s["caption"]).upper() if sh else _clean(s["caption"])
            lines.append(f"Dialogue: 0,{_ts(t_out + 0.1)},{_ts(t_out + dur - 0.1)},Main,,0,0,0,,{txt}")
        t_out += dur
    return head + "\n".join(lines) + "\n"
