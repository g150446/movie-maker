#!/usr/bin/env python3
"""
肩手術説明スライド → ナレーション付き動画 生成スクリプト
- LLM: OpenRouter google/gemini-2.5-flash-lite
- TTS: OpenAI gpt-4o-mini-tts
- 動画結合: ffmpeg
"""

import os
import re
import subprocess
import sys
import fitz  # PyMuPDF
import requests
from pathlib import Path
from openai import OpenAI


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
            os.environ[key] = value  # .env の値で常に上書き


load_dotenv()

# --- 設定 ---
PDF_PATH = "source-pdf/肩手術前説明_患者向けスライドv3.pptx.pdf"
SOURCE_MOVIES_DIR = "source-movies"
WORK_DIR = Path("work")
OUTPUT_DIR = Path("output")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# YouTubeリンク → ローカルMP4 対応表
YOUTUBE_MAP = {
    "3OaWXXEdS7g": f"{SOURCE_MOVIES_DIR}/腱板修復について.mp4",
    "mztWM1LhefK": f"{SOURCE_MOVIES_DIR}/関節唇修復について.mp4",
}

TTS_VOICE = "alloy"  # OpenAI TTS voice: alloy, echo, fable, onyx, nova, shimmer

# --- ディレクトリ準備 ---
(WORK_DIR / "slides").mkdir(parents=True, exist_ok=True)
(WORK_DIR / "narrations").mkdir(parents=True, exist_ok=True)
(WORK_DIR / "audio").mkdir(parents=True, exist_ok=True)
(WORK_DIR / "clips").mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_youtube_id(url: str) -> str | None:
    """URLからYouTube動画IDを抽出"""
    patterns = [
        r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def parse_pdf(pdf_path: str):
    """
    PDFを解析し、各ページの情報を返す。
    戻り値: list of dict {
        'page_num': int (1-based),
        'text': str,
        'image_path': str,
        'youtube_mp4': str | None  # ローカルMP4パス
    }
    """
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        page_num = i + 1
        image_path = str(WORK_DIR / "slides" / f"page_{page_num:02d}.png")

        # ページ画像保存（解像度2倍）
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        pix.save(image_path)
        print(f"  [PDF] ページ {page_num} → {image_path}")

        # テキスト抽出
        text = page.get_text("text").strip()

        # リンク検出
        youtube_mp4 = None
        links = page.get_links()
        for link in links:
            uri = link.get("uri", "")
            yt_id = extract_youtube_id(uri)
            if yt_id and yt_id in YOUTUBE_MAP:
                youtube_mp4 = YOUTUBE_MAP[yt_id]
                print(f"  [PDF] ページ {page_num} にYouTubeリンク検出: {yt_id} → {youtube_mp4}")
                break

        pages.append({
            "page_num": page_num,
            "text": text,
            "image_path": image_path,
            "youtube_mp4": youtube_mp4,
        })

    doc.close()
    return pages


def generate_narration(page_num: int, slide_text: str) -> str:
    """OpenRouter (Gemini) でナレーション原稿を生成"""
    narration_path = WORK_DIR / "narrations" / f"page_{page_num:02d}.txt"

    if narration_path.exists():
        print(f"  [LLM] ページ {page_num} ナレーションはキャッシュ済みをスキップ")
        return narration_path.read_text(encoding="utf-8")

    prompt = f"""あなたは医療機関の患者向けビデオのナレーターです。
以下は肩手術前説明スライドの1ページ分のテキストです。
このスライドの内容を、手術を控えた患者に向けて、
落ち着いた・やさしい・わかりやすい口調の日本語ナレーションとして作成してください。

条件：
- 読み上げ時間の目安：20〜40秒程度（約100〜200文字）
- 専門用語はできるだけ平易な言葉に言い換える
- 「このスライドでは」「次に」などの接続表現は自然に使用可
- ナレーション本文のみを出力し、前置き・説明・カギカッコ等は不要

--- スライドテキスト ---
{slide_text if slide_text else "（テキストなし：図やイラストのみのページです）"}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
        "X-Title": "shoulder-surgery-video",
    }
    payload = {
        "model": "google/gemini-2.5-flash-lite",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    narration = response.json()["choices"][0]["message"]["content"].strip()

    narration_path.write_text(narration, encoding="utf-8")
    print(f"  [LLM] ページ {page_num} ナレーション生成完了 ({len(narration)}文字)")
    return narration


def normalize_for_tts(text: str) -> str:
    """TTS用テキスト正規化: 二重読み・誤読を修正"""
    # 漢字（ひらがな）→ ひらがな のみに（括弧内の読みだけ残す）
    # 例: 腱板（けんばん）→ けんばん
    text = re.sub(r'[^\s（）]*（([ぁ-んァ-ン]+)）', r'\1', text)

    # 医療用語の誤読修正（漢字 → 正しいひらがな）
    TERM_FIXES = {
        "関節唇": "かんせつしん",
        "肩峰下除圧術": "けんぽうかじょあつじゅつ",
    }
    for kanji, reading in TERM_FIXES.items():
        text = text.replace(kanji, reading)

    return text


def generate_audio(page_num: int, narration_text: str) -> str:
    """OpenAI TTS (gpt-4o-mini-tts) で音声合成"""
    audio_path = str(WORK_DIR / "audio" / f"page_{page_num:02d}.mp3")

    if Path(audio_path).exists():
        print(f"  [TTS] ページ {page_num} 音声はキャッシュ済みをスキップ")
        return audio_path

    tts_text = normalize_for_tts(narration_text)
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=TTS_VOICE,
        input=tts_text,
        response_format="mp3",
    )
    response.stream_to_file(audio_path)
    print(f"  [TTS] ページ {page_num} 音声生成完了 → {audio_path}")
    return audio_path


def make_slide_clip(page_num: int, image_path: str, audio_path: str) -> str:
    """PNG + MP3 → MP4クリップ（音声長に合わせた静止画動画）"""
    clip_path = str(WORK_DIR / "clips" / f"clip_{page_num:02d}.mp4")

    if Path(clip_path).exists():
        print(f"  [ffmpeg] ページ {page_num} クリップはキャッシュ済みをスキップ")
        return clip_path

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-shortest",
        clip_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffmpeg] エラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg failed for page {page_num}")
    print(f"  [ffmpeg] ページ {page_num} クリップ作成完了 → {clip_path}")
    return clip_path


def scale_mp4(src_path: str, dst_path: str) -> str:
    """既存MP4を1920x1080にスケール（アスペクト比維持・レターボックス）"""
    if Path(dst_path).exists():
        print(f"  [ffmpeg] スケール済みクリップをスキップ: {dst_path}")
        return dst_path

    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-c:v", "libx264",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        dst_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffmpeg] スケールエラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg scale failed for {src_path}")
    print(f"  [ffmpeg] スケール完了 → {dst_path}")
    return dst_path


def concat_clips(clip_paths: list[str], output_path: str):
    """全クリップをffmpegのconcatフィルタで結合（タイムスタンプ完全正規化）"""
    n = len(clip_paths)

    # -i input ... を並べる
    inputs = []
    for p in clip_paths:
        inputs += ["-i", p]

    # filter_complex: [0:v][0:a][1:v][1:a]...concat=n=N:v=1:a=1[outv][outa]
    filter_parts = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    filter_complex = f"{filter_parts}concat=n={n}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffmpeg] 結合エラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError("ffmpeg concat failed")
    print(f"\n[完了] 最終動画 → {output_path}")


def main():
    print("=== 肩手術説明動画 生成開始 ===\n")

    if not OPENROUTER_API_KEY:
        print("エラー: 環境変数 OPENROUTER_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)
    if not OPENAI_API_KEY:
        print("エラー: OPENAI_API_KEY が .env または環境変数に設定されていません", file=sys.stderr)
        sys.exit(1)

    # Step 1: PDF解析
    print("--- Step 1: PDF解析 ---")
    pages = parse_pdf(PDF_PATH)
    print(f"  合計 {len(pages)} ページ検出\n")

    # ページ7・8はローカルMP4で置き換える（スライド・ナレーションをスキップ）
    SKIP_PAGES = {7, 8}
    # ページ7の後に挿入するローカルMP4（順番通り）
    INSERT_AFTER_PAGE6 = [
        f"{SOURCE_MOVIES_DIR}/腱板修復について.mp4",
        f"{SOURCE_MOVIES_DIR}/関節唇修復について.mp4",
    ]

    clip_paths: list[str] = []
    inserted_mp4s = False

    for page in pages:
        page_num = page["page_num"]

        # ページ7・8はスキップ、代わりにローカルMP4を挿入
        if page_num in SKIP_PAGES:
            if not inserted_mp4s:
                print(f"--- ページ7・8をスキップ → ローカルMP4を挿入 ---")
                for i, mp4_src in enumerate(INSERT_AFTER_PAGE6):
                    mp4_name = Path(mp4_src).stem
                    scaled_path = str(WORK_DIR / "clips" / f"clip_insert_{i+1:02d}_{mp4_name}.mp4")
                    scaled = scale_mp4(mp4_src, scaled_path)
                    clip_paths.append(scaled)
                    print()
                inserted_mp4s = True
            continue

        print(f"--- ページ {page_num} 処理中 ---")

        # Step 2: ナレーション生成
        narration = generate_narration(page_num, page["text"])

        # Step 3: TTS音声生成
        audio_path = generate_audio(page_num, narration)

        # Step 4: スライドクリップ作成
        clip = make_slide_clip(page_num, page["image_path"], audio_path)
        clip_paths.append(clip)

        print()

    # Step 5: 全クリップ結合
    print("--- Step 5: 全クリップ結合 ---")
    output_path = str(OUTPUT_DIR / "final.mp4")
    concat_clips(clip_paths, output_path)


if __name__ == "__main__":
    main()
