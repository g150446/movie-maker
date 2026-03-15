#!/usr/bin/env python3
"""
肩手術説明スライド → ナレーション付き動画 生成スクリプト
- TTS: OpenAI gpt-4o-mini-tts（alloy 音声）
- 動画結合: ffmpeg
"""

import os
import re
import subprocess
import sys
import fitz  # PyMuPDF
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
PDF_PATH = "source-pdf/肩手術前説明_患者向けスライドv6.pptx.pdf"
NARRATIONS_PATH = "source-narrations/肩の手術の説明スライドnarrations_allｖ6.txt"
PRONUNCIATIONS_PATH = "source-narrations/pronunciations.md"
SOURCE_MOVIES_DIR = "source-movies"
SOURCE_TRANSCRIPTIONS_DIR = Path("source-transcriptions")
WORK_DIR = Path("work")
OUTPUT_DIR = Path("output")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# YouTubeリンク → ローカルMP4 対応表
YOUTUBE_MAP = {
    "3OaWXXEdS7g": f"{SOURCE_MOVIES_DIR}/腱板修復について.mp4",
    "mztWM1LhefK": f"{SOURCE_MOVIES_DIR}/関節唇修復について.mp4",
}

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICES = ["alloy"]
TTS_SPEED = 1.08
TTS_INSTRUCTIONS = (
    "日本語の患者向け医療説明として、自然で聞き取りやすく、落ち着いた口調で読み上げてください。"
    "ただし全体のテンポは通常より少し早めにしてください。"
    "漢字の読み間違いを避け、特に『しゅじゅつ』『ににんさんきゃく』は正確に発音してください。"
)
INSERT_PLAYBACK_RATE = 1.7
INSERT_VIDEO_SPECS = [
    {
        "page_num": 10,
        "source_mp4": f"{SOURCE_MOVIES_DIR}/腱板修復について.mp4",
        "script_path": SOURCE_TRANSCRIPTIONS_DIR / "腱板修復について_患者向けv5.txt",
        "clip_stem": "clip_insert_01_腱板修復について",
    },
    {
        "page_num": 11,
        "source_mp4": f"{SOURCE_MOVIES_DIR}/関節唇修復について.mp4",
        "script_path": SOURCE_TRANSCRIPTIONS_DIR / "関節唇修復について_患者向けv5.txt",
        "clip_stem": "clip_insert_02_関節唇修復について",
    },
]

# --- ディレクトリ準備 ---
(WORK_DIR / "slides").mkdir(parents=True, exist_ok=True)
(WORK_DIR / "narrations").mkdir(parents=True, exist_ok=True)
for _voice in TTS_VOICES:
    (WORK_DIR / _voice / "audio").mkdir(parents=True, exist_ok=True)
    (WORK_DIR / _voice / "clips").mkdir(parents=True, exist_ok=True)
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


def load_narrations(path: str) -> dict[int, str]:
    """テキストファイルから【ページ ...】区切りでナレーションを順番に読み込む"""
    text = Path(path).read_text(encoding="utf-8")
    parts = re.split(r'【ページ[^】]*】', text)
    # parts[0] は区切り前（空or不要）、parts[1]からがページ1,2,...に対応
    return {i: part.strip() for i, part in enumerate(parts[1:], start=1)}


def generate_narration(page_num: int, narrations: dict[int, str]) -> str:
    """テキストファイルからナレーション原稿を読み込む"""
    narration = narrations.get(page_num, "")
    if not narration:
        print(f"  [警告] ページ {page_num} のナレーションが見つかりません", file=sys.stderr)
    narration_path = WORK_DIR / "narrations" / f"page_{page_num:02d}.txt"
    narration_path.write_text(narration, encoding="utf-8")
    print(f"  [ナレーション] ページ {page_num} 読み込み完了 ({len(narration)}文字)")
    return narration


def load_pronunciations(path: str) -> dict[str, str]:
    """pronunciations.mdのMarkdownテーブルから漢字→読み方の対応表を読み込む"""
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|") or "漢字" in line or "---" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            result[parts[0]] = parts[1]
    return result


def normalize_for_tts(text: str) -> str:
    """TTS用テキスト正規化: 二重読み・誤読を修正"""
    # 漢字（ひらがな）→ ひらがな のみに（括弧内の読みだけ残す）
    # 例: 腱板（けんばん）→ けんばん
    text = re.sub(r'[^\s（）]*（([ぁ-んァ-ン]+)）', r'\1', text)

    # 医療用語の誤読修正（pronunciations.md + 追加の固定ルール）
    term_fixes = load_pronunciations(PRONUNCIATIONS_PATH)
    term_fixes.update({
        "手術": "しゅじゅつ",
        "肩峰下除圧術": "けんぽうかじょあつじゅつ",
    })
    for kanji, reading in term_fixes.items():
        text = text.replace(kanji, reading)

    return text


def is_output_fresh(output_path: str, input_paths: list[str | Path]) -> bool:
    """出力が入力群より新しいときのみキャッシュを再利用"""
    output = Path(output_path)
    if not output.exists():
        return False

    output_mtime = output.stat().st_mtime
    for input_path in input_paths:
        input_file = Path(input_path)
        if not input_file.exists() or input_file.stat().st_mtime > output_mtime:
            return False
    return True


def generate_audio(asset_id: str, narration_text: str, voice: str, label: str | None = None) -> str:
    """OpenAI TTS (tts-1-hd) で音声合成"""
    audio_dir = WORK_DIR / voice / "audio"
    audio_path = str(audio_dir / f"{asset_id}.mp3")
    cache_text_path = audio_dir / f"{asset_id}.txt"
    label = label or asset_id
    tts_text = normalize_for_tts(narration_text)

    cache_key = f"model={TTS_MODEL}\n{tts_text}"
    if Path(audio_path).exists() and cache_text_path.exists():
        cached_text = cache_text_path.read_text(encoding="utf-8")
        if cached_text == cache_key:
            print(f"  [TTS/{voice}] {label} 音声はキャッシュ済みをスキップ")
            return audio_path

    client = OpenAI(api_key=OPENAI_API_KEY)
    with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=voice,
        input=tts_text,
        instructions=TTS_INSTRUCTIONS,
        speed=TTS_SPEED,
        response_format="mp3",
    ) as response:
        response.stream_to_file(audio_path)
    cache_text_path.write_text(cache_key, encoding="utf-8")
    print(f"  [TTS/{voice}] {label} 音声生成完了 → {audio_path}")
    return audio_path


def make_slide_clip(page_num: int, image_path: str, audio_path: str, voice: str) -> str:
    """PNG + MP3 → MP4クリップ（音声長に合わせた静止画動画）"""
    clip_path = str(WORK_DIR / voice / "clips" / f"clip_{page_num:02d}.mp4")

    if is_output_fresh(clip_path, [image_path, audio_path]):
        print(f"  [ffmpeg/{voice}] ページ {page_num} クリップはキャッシュ済みをスキップ")
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
        print(f"  [ffmpeg/{voice}] エラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg failed for page {page_num}")
    print(f"  [ffmpeg/{voice}] ページ {page_num} クリップ作成完了 → {clip_path}")
    return clip_path


def get_media_duration(path: str) -> float:
    """ffprobe でメディア長さ（秒）を取得"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffprobe] 長さ取得エラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError(f"ffprobe failed for {path}")
    return float(result.stdout.strip())


def make_insert_clip(spec: dict, voice: str) -> str:
    """挿入動画を無音1.7倍速＋日本語ナレーション付きクリップに変換"""
    clip_path = str(WORK_DIR / voice / "clips" / f"{spec['clip_stem']}.mp4")

    narration_text = spec["script_path"].read_text(encoding="utf-8").strip()
    audio_path = generate_audio(
        f"{spec['clip_stem']}_audio",
        narration_text,
        voice,
        f"挿入動画ページ {spec['page_num']}",
    )

    if is_output_fresh(clip_path, [spec["source_mp4"], spec["script_path"], audio_path]):
        print(f"  [ffmpeg/{voice}] 挿入動画クリップをスキップ: {clip_path}")
        return clip_path

    source_duration = get_media_duration(spec["source_mp4"])
    video_duration = source_duration / INSERT_PLAYBACK_RATE
    audio_duration = get_media_duration(audio_path)
    extra_video_pad = max(audio_duration - video_duration, 0.0)
    extra_audio_pad = max(video_duration - audio_duration, 0.0)
    target_duration = max(video_duration, audio_duration)

    video_filter = (
        f"setpts=PTS/{INSERT_PLAYBACK_RATE},"
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
        "fps=30"
    )
    if extra_video_pad > 0:
        video_filter += f",tpad=stop_mode=clone:stop_duration={extra_video_pad:.3f}"

    audio_filter = "anull"
    if extra_audio_pad > 0:
        audio_filter = f"apad=pad_dur={extra_audio_pad:.3f}"

    cmd = [
        "ffmpeg", "-y",
        "-i", spec["source_mp4"],
        "-i", audio_path,
        "-filter_complex", f"[0:v]{video_filter}[v];[1:a]{audio_filter}[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-t", f"{target_duration:.3f}",
        "-c:v", "libx264",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        clip_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ffmpeg/{voice}] 挿入動画変換エラー: {result.stderr[-500:]}", file=sys.stderr)
        raise RuntimeError(f"ffmpeg insert clip failed for {spec['source_mp4']}")
    print(f"  [ffmpeg/{voice}] 挿入動画クリップ作成完了 → {clip_path}")
    return clip_path


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



def build_voice(voice: str, pages: list, narrations: dict, insert_specs_by_page: dict, skip_pages: set):
    """1つの音声プリセットで全クリップを生成し、最終動画を出力する"""
    print(f"\n=== 音声: {voice} ===")
    voice_output_dir = OUTPUT_DIR / voice
    voice_output_dir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[str] = []

    for page in pages:
        page_num = page["page_num"]

        if page_num in skip_pages:
            print(f"--- [{voice}] ページ {page_num} は挿入動画を処理中 ---")
            clip_paths.append(make_insert_clip(insert_specs_by_page[page_num], voice))
            print()
            continue

        print(f"--- [{voice}] ページ {page_num} 処理中 ---")

        narration = generate_narration(page_num, narrations)
        audio_path = generate_audio(f"page_{page_num:02d}", narration, voice, f"ページ {page_num}")
        clip = make_slide_clip(page_num, page["image_path"], audio_path, voice)
        clip_paths.append(clip)

        print()

    print(f"--- [{voice}] 全クリップ結合 ---")
    output_path = str(voice_output_dir / "final.mp4")
    concat_clips(clip_paths, output_path)


def main():
    print("=== 肩手術説明動画 生成開始 ===\n")

    if not OPENAI_API_KEY:
        print("エラー: OPENAI_API_KEY が .env または環境変数に設定されていません", file=sys.stderr)
        sys.exit(1)

    # Step 1: ナレーション読み込み
    print("--- Step 1: ナレーション読み込み ---")
    narrations = load_narrations(NARRATIONS_PATH)
    print(f"  合計 {len(narrations)} ページ分のナレーション読み込み完了\n")

    # Step 2: PDF解析（スライド画像は全音声共通）
    print("--- Step 2: PDF解析 ---")
    pages = parse_pdf(PDF_PATH)
    print(f"  合計 {len(pages)} ページ検出\n")

    insert_specs_by_page = {spec["page_num"]: spec for spec in INSERT_VIDEO_SPECS}
    skip_pages = set(insert_specs_by_page)

    # Step 3〜6: 音声ごとにクリップ生成・結合
    for voice in TTS_VOICES:
        build_voice(voice, pages, narrations, insert_specs_by_page, skip_pages)

    print("\n=== すべての音声の動画生成が完了しました ===")
    for voice in TTS_VOICES:
        print(f"  {voice}: {OUTPUT_DIR / voice / 'final.mp4'}")


if __name__ == "__main__":
    main()
