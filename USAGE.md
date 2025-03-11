# 写真評価ツール（Whale）使用方法

## 準備

1. uvを使用して環境をセットアップします：

```bash
# 新しい仮想環境を作成して初期化
uv init

# 必要なパッケージをインストール
uv pip install -r requirements.txt
```

**従来のpipを使用する場合：**
```bash
# 仮想環境を作成（オプション）
python -m venv venv
source venv/bin/activate  # Linuxの場合
# または
venv\Scripts\activate     # Windowsの場合

# 必要なパッケージをインストール
pip install -r requirements.txt
```

2. `.env`ファイルを編集して、使用するAPIの設定を行います：

### OpenAI APIを使用する場合（デフォルト）

```
OPENAI_API_KEY=your_api_key_here
DEFAULT_API=openai
```

OpenAI APIキーは[OpenAIのダッシュボード](https://platform.openai.com/api-keys)から取得できます。

### Ollama Visionを使用する場合

```
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llava
DEFAULT_API=ollama
```

Ollamaは、ローカルで実行できるLLMのランタイムです。以下の手順でセットアップします：

1. [Ollama](https://ollama.com/)をインストール
2. LLaVAなどのVisionモデルをダウンロード：`ollama pull llava`
3. Ollamaサーバーを起動：`ollama serve`

## 基本的な使用方法

### 特定のフォルダ内の写真を評価する

**uvを使用する場合（推奨）：**
```bash
uv run main.py --folder /path/to/your/photos
```

**従来のpythonを使用する場合：**
```bash
python main.py --folder /path/to/your/photos
```

### 評価する写真の数を制限する

```bash
uv run main.py --folder /path/to/your/photos --max 10
```

### フォルダを監視して新しい写真を自動的に評価する（将来的な機能）

```bash
uv run main.py --folder /path/to/your/photos --watch
```

監視間隔を変更する場合：

```bash
uv run main.py --folder /path/to/your/photos --watch --interval 120
```

### 並列処理を使用して処理を高速化する

大量の画像を処理する場合、並列処理を使用して処理時間を短縮できます：

```bash
# ワーカー数を増やす（デフォルト: 4）
uv run main.py --folder /path/to/your/photos --workers 8

# バッチサイズを変更する（デフォルト: 10）
uv run main.py --folder /path/to/your/photos --batch-size 20

# 画像のリサイズサイズを変更する（デフォルト: 1024ピクセル）
uv run main.py --folder /path/to/your/photos --resize 800
```

複数のオプションを組み合わせることもできます：

```bash
uv run main.py --folder /path/to/your/photos --workers 8 --batch-size 20 --resize 800 --max 100
```

### Ollama Visionを使用する

コマンドラインからOllama Visionを使用する場合：

```bash
# Ollama Visionを使用して評価
uv run main.py --folder /path/to/your/photos --api ollama

# 特定のOllamaモデルを指定
uv run main.py --folder /path/to/your/photos --api ollama --ollama-model bakllava

# Ollamaのホストを指定（リモートサーバーの場合）
uv run main.py --folder /path/to/your/photos --api ollama --ollama-host http://192.168.1.100:11434
```

## 評価結果

評価が完了すると、以下のファイルが生成されます：

1. `evaluation_results.json` - 評価結果の詳細なJSONデータ
2. `evaluation_results.csv` - 評価結果のCSVデータ
3. `summary.txt` - 評価結果のサマリー
4. `good_photos/` - 良い写真のコピー（スコア付きのファイル名）

## 評価基準

写真は以下の観点から1〜10の数値で評価されます：

1. 構図（バランス、フレーミング、視線誘導）
2. 露出（明るさ、コントラスト、ダイナミックレンジ）
3. 色彩（色のバランス、彩度、色温度）
4. 焦点（シャープネス、被写界深度、ボケ具合）
5. 被写体（主題の明確さ、表現力、魅力）
6. 全体的な印象（感情的なインパクト、記憶に残るか）

総合評価スコアが閾値（デフォルト: 7.5）以上の写真が「良い写真」と判断されます。
閾値は`.env`ファイルの`QUALITY_THRESHOLD`で変更できます。

## トラブルシューティング

### APIキーエラー

```
ValueError: OpenAI APIキーが設定されていません
```

`.env`ファイルに有効なOpenAI APIキーが設定されているか確認してください。

### 画像が見つからない

```
評価する画像がありません
```

指定したフォルダに画像ファイルが存在するか確認してください。
サポートされている画像形式は: .jpg, .jpeg, .png, .gif, .bmp, .webp です。

### APIレート制限

OpenAI APIには使用制限があります。大量の画像を評価する場合は、
`--max`オプションを使用して一度に評価する画像数を制限することをお勧めします。

### Ollamaの接続エラー

```
Ollama Visionでの画像評価中にエラーが発生しました: HTTPConnectionPool(host='localhost', port=11434)
```

以下を確認してください：
1. Ollamaがインストールされ、実行されているか
2. 指定したモデル（例：llava）がダウンロードされているか（`ollama list`で確認）
3. ホストとポートが正しいか（デフォルト：http://localhost:11434）

### Ollamaのモデルエラー

```
Ollamaの出力からJSONを抽出できませんでした
```

使用しているOllamaモデルがVision機能をサポートしているか確認してください。
サポートされているモデルには以下があります：
- llava
- bakllava
- moondream
