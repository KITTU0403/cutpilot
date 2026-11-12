import os
from pathlib import Path

DATA = Path(os.getenv("DATA_DIR", "data"))
DATA.mkdir(parents=True, exist_ok=True)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
MAX_OUT_SECONDS = 300
RATIOS = {
    "9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080),
    "4:5": (1080, 1350), "4:3": (1440, 1080), "21:9": (1920, 822),
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
