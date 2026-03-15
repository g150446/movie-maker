# 肩手術説明動画 生成スクリプト

PDF スライドとナレーションテキストから、OpenAI TTS + ffmpeg を使ってナレーション付き動画を自動生成します。  
Alloy（女性声）と Onyx（男性声）の 2 種類の音声で同時に出力します。

---

## 前提条件

| ツール | バージョン目安 |
|--------|--------------|
| Python | 3.11 以上 |
| ffmpeg | 5.x 以上（`ffmpeg`, `ffprobe` が PATH に通っていること） |
| OpenAI API キー | `tts-1-hd` モデルの利用権限があること |

---

## セットアップ

```bash
# 1. リポジトリクローン
git clone https://github.com/g150446/movie-maker.git
cd movie-maker

# 2. 仮想環境を作成・有効化
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 依存パッケージをインストール
pip install openai pymupdf

# 4. APIキーを設定
cp .env.example .env       # .env.example がない場合は下記を参考に作成
echo 'OPENAI_API_KEY=sk-...' > .env
```

---

## 実行方法

```bash
source venv/bin/activate
python generate.py
```

実行すると以下の処理が順に行われます。

1. ナレーションテキストを読み込む
2. PDF を解析してスライド画像を生成（`work/slides/`）
3. Alloy・Onyx それぞれの音声で TTS 音声を生成（`work/{voice}/audio/`）
4. 各ページのスライドクリップを作成（`work/{voice}/clips/`）
5. 全クリップを結合して最終動画を出力（`output/{voice}/final.mp4`）

---

## 入力ファイル

| パス | 説明 |
|------|------|
| `source-pdf/肩手術前説明_患者向けスライドv6.pptx.pdf` | スライド PDF（ページ画像の元データ） |
| `source-narrations/肩の手術の説明スライドnarrations_allｖ6.txt` | ナレーション原稿（`【ページ N】` 区切り） |
| `source-narrations/pronunciations.md` | 漢字の読み方辞書（Markdown テーブル形式） |
| `source-movies/腱板修復について.mp4` | ページ 10 に挿入する手術動画 |
| `source-movies/関節唇修復について.mp4` | ページ 11 に挿入する手術動画 |
| `source-transcriptions/腱板修復について_患者向けv5.txt` | ページ 10 挿入動画のナレーション原稿 |
| `source-transcriptions/関節唇修復について_患者向けv5.txt` | ページ 11 挿入動画のナレーション原稿 |

### ナレーションファイルの形式

```
【ページ 1】
ここに 1 ページ目のナレーション本文を書きます。

【ページ 2】
2 ページ目のナレーション本文。
```

### pronunciations.md の形式

```markdown
| 漢字 | 読み方 |
|------|--------|
| 腱板 | けんばん |
| 関節唇 | かんせつしん |
```

---

## 出力ファイル

| パス | 内容 |
|------|------|
| `output/alloy/final.mp4` | Alloy（女性声）版の完成動画 |
| `output/onyx/final.mp4` | Onyx（男性声）版の完成動画 |

---

## キャッシュについて

生成済みの音声ファイル（`.mp3`）とクリップ（`.mp4`）はキャッシュされ、同一テキスト・同一入力ファイルであれば再生成をスキップします。  
ソースファイルを更新した場合や音声を完全に再生成したい場合は、対応する `work/` ディレクトリを削除してください。

```bash
# キャッシュを全削除して最初から再生成
rm -rf work/alloy work/onyx work/slides work/narrations
```

---

## 環境変数

| 変数名 | 説明 |
|--------|------|
| `OPENAI_API_KEY` | OpenAI の API キー（必須） |

`.env` ファイルに記載するか、環境変数として事前にエクスポートしてください。
