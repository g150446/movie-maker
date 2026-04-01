# 肩手術説明動画 生成スクリプト — はじめてのセットアップガイド

このリポジトリを使うと、PDF スライドとナレーションテキストから **ナレーション付き説明動画** を自動生成できます。  
このガイドでは、プログラミング未経験の方が **Claude Code（AI コーディングアシスタント）** を使ってこのツールをセットアップし、操作できるようになるまでの手順を説明します。

> 📁 技術的な詳細情報は [`docs/README_technical.md`](docs/README_technical.md) を、保守・運用ガイドは [`docs/maintenance.md`](docs/maintenance.md) をご覧ください。

---

## このツールでできること

- PDF スライドの各ページに音声（ナレーション）を付けた動画を自動生成
- 指定した手術動画を途中に挿入
- OpenAI の音声合成（TTS）を使って自然な日本語音声を生成

---

## Step 1: Anthropic アカウントの作成と Pro サブスクリプションへの登録

Claude Code を使うには **Anthropic のアカウント** と **Pro サブスクリプション** が必要です。

1. ブラウザで [https://console.anthropic.com](https://console.anthropic.com) を開く
2. 「Sign up」をクリックしてメールアドレスとパスワードを登録
3. 届いた確認メールのリンクをクリックして認証を完了
4. ログイン後、左メニューの **「Subscriptions」** から **Pro プラン** に登録

> 💡 Claude Code の利用には Anthropic のサブスクリプション（Claude Pro / Max など）が必要です。
> [https://www.anthropic.com/pricing](https://www.anthropic.com/pricing) で料金プランをご確認ください。

---

## Step 2: Git のインストール

ソースコードをダウンロードするために **Git** が必要です。

### Mac の場合

ターミナルを開いて以下を実行してください（初回のみ自動でインストールされます）：

```bash
git --version
```

「Command Line Tools」のインストール確認ダイアログが表示された場合は「インストール」をクリックしてください。  
すでにインストール済みの場合はバージョンが表示されます。

### Windows の場合

1. [https://git-scm.com/download/win](https://git-scm.com/download/win) を開く
2. 「64-bit Git for Windows Setup」をダウンロードしてインストール
3. インストール中の選択肢はすべてデフォルトのままで OK
4. インストール完了後、スタートメニューから **「Git Bash」** を起動して以下を確認：

```bash
git --version
```

バージョン番号が表示されれば成功です。

---

## Step 3: Node.js のインストール

Claude Code は Node.js が必要です。

### Mac の場合

```bash
# Homebrew がない場合はまずインストール
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Node.js をインストール
brew install node
```

### Windows の場合

1. [https://nodejs.org/](https://nodejs.org/) を開く
2. 「LTS（推奨版）」をダウンロードしてインストール
3. インストール中の選択肢はすべてデフォルトのままで OK

---

## Step 4: Claude Code のインストール

### Mac の場合

ターミナルで以下を実行：

```bash
npm install -g @anthropic-ai/claude-code
```

### Windows の場合

Git Bash（またはコマンドプロンプト）で以下を実行：

```bash
npm install -g @anthropic-ai/claude-code
```

### ログイン

インストール後、以下のコマンドを実行してブラウザで Anthropic アカウントにログインします：

```bash
claude login
```

ブラウザが自動で開くので、Anthropic アカウントでログインしてください。

---

## Step 5: リポジトリのクローン（ダウンロード）

### Mac の場合

ターミナルで以下を実行：

```bash
git clone https://github.com/g150446/movie-maker.git
cd movie-maker
```

### Windows の場合

Git Bash で以下を実行：

```bash
git clone https://github.com/g150446/movie-maker.git
cd movie-maker
```

---

## Step 6: Python のインストール確認

### Mac の場合

```bash
python3 --version
```

バージョンが **3.11 以上** であれば OK です。  
インストールされていない場合は [https://www.python.org/downloads/](https://www.python.org/downloads/) からダウンロードしてください。

### Windows の場合

Git Bash またはコマンドプロンプトで：

```bash
python --version
```

インストールされていない場合は [https://www.python.org/downloads/](https://www.python.org/downloads/) からダウンロードしてください。  
インストール時に **「Add Python to PATH」にチェックを入れる** のを忘れずに！

---

## Step 7: ffmpeg のインストール

動画・音声の変換に **ffmpeg** が必要です。

### Mac の場合

```bash
brew install ffmpeg
```

### Windows の場合

```bash
winget install Gyan.FFmpeg
```

> winget がない場合は [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) から手動でダウンロードし、PATH を設定してください。

インストール後、以下で確認：

```bash
ffmpeg -version
```

---

## Step 8: プロジェクトのセットアップ

### Mac の場合

```bash
# 仮想環境の作成と有効化
python3 -m venv venv
source venv/bin/activate

# 依存パッケージのインストール
pip install openai pymupdf
```

### Windows の場合

Git Bash で：

```bash
# 仮想環境の作成と有効化
python -m venv venv
source venv/Scripts/activate

# 依存パッケージのインストール
pip install openai pymupdf
```

---

## Step 9: Claude Code で操作する

セットアップが完了したら、**Claude Code** を使ってプロジェクトを AI と一緒に操作できます。  
リポジトリのフォルダ内で以下のコマンドを実行してください：

### Mac の場合

```bash
source venv/bin/activate
claude
```

### Windows の場合

```bash
source venv/Scripts/activate
claude
```

Claude Code が起動したら、日本語で自由に指示を入力できます。

### 指示の例

```
動画を生成してください
```

```
2つ目の挿入動画（関節唇修復について）のスピードを1倍に戻してください
```

```
ナレーションのテキストを変更したので、キャッシュをクリアして動画を再生成してください
```

> 💡 Claude Code はこのリポジトリのコードを理解して、必要な変更や実行を自動で行います。  
> わからないことは「〇〇はどうすればいいですか？」と聞くだけで大丈夫です。

---

## 必須ファイルの準備

このツールで動画を生成するには、以下の 2 つのディレクトリにソースファイルを保存する必要があります。

### `source-movies/` — 挿入用の手術動画

- 術中に挿入する動画ファイル（.mp4 など）を保存
- ファイル名は任意ですが、内容が分かりやすい名前を推奨（例：`anchor-insertion.mp4`）
- 動画の挿入位置や再生速度は Claude Code に指示して調整可能

### `source-pdf/` — 説明スライド PDF

- 手術説明のスライド資料（PDF 形式）を保存
- 各ページが動画の 1 シーンに対応
- PDF のページ順にスライドが表示され、それぞれにナレーションが付与される

> 📌 **注意**: これらのディレクトリは Git で管理されますが、中に含まれる動画・PDF ファイル自体は `.gitignore` により Git の対象外となります。大容量ファイルの誤コミットを防ぐためです。

---

## 詳細情報

| ドキュメント | 内容 |
|-------------|------|
| [`docs/README_technical.md`](docs/README_technical.md) | 入力ファイル形式・出力先・設定項目の詳細 |
| [`docs/maintenance.md`](docs/maintenance.md) | アーキテクチャ・バージョンアップ・トラブルシューティング |
