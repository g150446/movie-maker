#!/usr/bin/env python3
"""source-movies/ の MP4 を Groq Whisper で文字起こしする"""

import os
from pathlib import Path
from groq import Groq


def load_dotenv(path: str = ".env"):
    """シンプルな .env ファイルローダー"""
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
SOURCE_MOVIES_DIR = Path("source-movies")
OUTPUT_DIR = Path("source-transcriptions")
OUTPUT_DIR.mkdir(exist_ok=True)

client = Groq(api_key=GROQ_API_KEY)

for mp4 in sorted(SOURCE_MOVIES_DIR.glob("*.mp4")):
    out_path = OUTPUT_DIR / f"{mp4.stem}.txt"
    if out_path.exists():
        print(f"スキップ（既存）: {out_path}")
        continue
    print(f"文字起こし中: {mp4.name} ...")
    with mp4.open("rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=f,
            language="en",
        )
    out_path.write_text(result.text, encoding="utf-8")
    print(f"  → {out_path} ({len(result.text)}文字)")
