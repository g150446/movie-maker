# 保守運用ガイド

## アーキテクチャ概要

```
source-pdf/          ← スライド PDF（入力）
source-narrations/   ← ナレーション原稿 + 発音辞書（入力）
source-transcriptions/ ← 挿入動画用ナレーション原稿（入力）
source-movies/       ← 挿入する手術動画（入力）
       ↓
   generate.py
       ↓
work/
  slides/            ← PDF から生成したスライド画像（共通）
  narrations/        ← ページごとのナレーションテキスト（共通）
  alloy/
    audio/           ← Alloy 音声の MP3 ファイル（キャッシュ）
    clips/           ← Alloy 動画クリップ（キャッシュ）
  onyx/
    audio/           ← Onyx 音声の MP3 ファイル（キャッシュ）
    clips/           ← Onyx 動画クリップ（キャッシュ）
       ↓
output/
  alloy/final.mp4    ← 完成動画（Alloy 版）
  onyx/final.mp4     ← 完成動画（Onyx 版）
```

**処理フロー（generate.py）:**

1. `load_narrations()` — ナレーションテキストをページ番号→テキストの dict に変換
2. `parse_pdf()` — PDF を 1 ページずつラスタライズして PNG を保存
3. `build_voice()` を音声ごとに実行
   - 通常ページ: `generate_narration()` → `generate_audio()` → `make_slide_clip()`
   - 挿入動画ページ（10・11）: `make_insert_clip()`（動画 1.7 倍速 + 日本語 TTS ナレーションを重畳）
4. `concat_clips()` — ffmpeg の concat フィルタで全クリップを 1 本に結合

---

## ファイル・ディレクトリ構成

```
movie-maker/
├── generate.py          # メインスクリプト
├── transcribe.py        # 音声文字起こしユーティリティ（別用途）
├── README.md            # 使い方ガイド
├── docs/
│   └── maintenance.md   # 本ドキュメント
├── source-pdf/          # 入力 PDF（バージョン管理）
├── source-narrations/   # ナレーション原稿・発音辞書
├── source-transcriptions/ # 挿入動画ナレーション原稿
├── source-movies/       # 挿入する手術動画
├── work/                # 生成中間ファイル（.gitignore 推奨）
├── output/              # 完成動画（.gitignore 推奨）
├── venv/                # Python 仮想環境（.gitignore 対象）
└── .env                 # APIキー（.gitignore 対象・コミット禁止）
```

---

## 主要設定項目（generate.py 冒頭）

| 定数 | デフォルト | 説明 |
|------|-----------|------|
| `PDF_PATH` | `source-pdf/...v6.pptx.pdf` | 入力 PDF のパス |
| `NARRATIONS_PATH` | `source-narrations/...v6.txt` | ナレーション原稿のパス |
| `PRONUNCIATIONS_PATH` | `source-narrations/pronunciations.md` | 発音辞書のパス |
| `TTS_MODEL` | `tts-1-hd` | OpenAI TTS モデル |
| `TTS_VOICES` | `["alloy", "onyx"]` | 生成する音声プリセット一覧 |
| `TTS_SPEED` | `1.08` | 読み上げ速度（1.0 = 通常速度） |
| `INSERT_PLAYBACK_RATE` | `1.7` | 挿入動画の再生速度倍率 |
| `INSERT_VIDEO_SPECS` | ページ 10・11 の設定リスト | 挿入動画の定義 |

---

## バージョンアップ時の手順

### 1. スライド PDF・ナレーションを新バージョンに更新する

1. `source-pdf/` に新バージョンの PDF を追加
2. `source-narrations/` に新バージョンのナレーション txt を追加
3. `generate.py` の `PDF_PATH` と `NARRATIONS_PATH` を新ファイル名に変更
4. 必要であれば `pronunciations.md` に新しい読み方を追記

### 2. 挿入動画のナレーションを更新する

1. `source-transcriptions/` に新バージョンのナレーション txt を追加
2. `generate.py` の `INSERT_VIDEO_SPECS` 内の `script_path` を更新

### 3. キャッシュをクリアして再生成する

```bash
rm -rf work/alloy work/onyx work/narrations
python generate.py
```

スライド画像（`work/slides/`）は PDF が変わらなければ保持して構いません。

---

## TTS モデル・音声の変更方法

### モデルを変更する

`generate.py` の `TTS_MODEL` を変更します。

```python
TTS_MODEL = "tts-1-hd"   # 高品質版（現在）
# TTS_MODEL = "tts-1"    # 標準版（低コスト）
```

> **注意**: `tts-1-hd` / `tts-1` は `instructions` パラメータを**サポートしません**。  
> `gpt-4o-mini-tts` などの新世代モデルに切り替える場合は `generate_audio()` 内の API 呼び出しに `instructions=` を追加する必要があります。

### 音声プリセットを変更・追加する

`TTS_VOICES` リストを編集します。利用可能な音声: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

```python
TTS_VOICES = ["alloy", "onyx"]   # 現在の設定
# TTS_VOICES = ["nova"]          # Nova のみ生成
# TTS_VOICES = ["alloy", "onyx", "nova"]  # 3 種類生成
```

新しい音声を追加した場合、その音声のキャッシュは `work/{voice}/` に作成されます。

---

## キャッシュ管理

### キャッシュの仕組み

- **TTS 音声キャッシュ**: `work/{voice}/audio/{asset_id}.txt` に正規化済みテキストを保存。次回実行時にテキストが一致すれば MP3 の再生成をスキップ。
- **クリップキャッシュ**: 出力 MP4 のタイムスタンプが入力（PNG・MP3）より新しければスキップ。

### キャッシュのクリア

```bash
# 特定音声のキャッシュのみ削除
rm -rf work/alloy/

# 全キャッシュ削除（スライド画像も含む）
rm -rf work/
```

---

## トラブルシューティング

### `OPENAI_API_KEY が設定されていません` エラー

`.env` ファイルに `OPENAI_API_KEY=sk-...` を記載するか、環境変数を設定してください。

```bash
export OPENAI_API_KEY=sk-...
```

### `ffmpeg failed for page N` エラー

- ffmpeg がインストールされているか確認: `which ffmpeg`
- スライド PNG が正常に生成されているか確認: `ls work/slides/`
- 対応する MP3 ファイルが壊れていないか確認し、壊れている場合はそのキャッシュを削除

### TTS 生成が途中で失敗する

OpenAI API のレート制限に達した可能性があります。しばらく待って再実行してください。途中まで生成されたファイルはキャッシュされるため、再実行時にスキップされます。

### 特定ページの音声を再生成したい

```bash
# 例: alloy の page_05 を再生成
rm work/alloy/audio/page_05.mp3 work/alloy/audio/page_05.txt
rm work/alloy/clips/clip_05.mp4
python generate.py
```

### 挿入動画クリップの音ズレ

`INSERT_PLAYBACK_RATE`（デフォルト 1.7）を調整してください。値を大きくすると動画が短くなり、ナレーションとの同期が変わります。

---

## 依存関係

| パッケージ | 用途 |
|-----------|------|
| `openai` | TTS API 呼び出し |
| `pymupdf` (fitz) | PDF のラスタライズ |
| `ffmpeg` (システム) | 動画・音声の変換・結合 |
| `ffprobe` (システム) | メディアの長さ取得 |
