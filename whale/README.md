# 写真評価ツール（Whale）

OpenAI APIを使用して、フォルダ内の写真を自動的に評価し、高品質な写真を選別するツールです。

## 機能

- 指定フォルダ内の画像ファイルを読み込み
- OpenAI APIを使用した画像の品質評価
- 評価結果に基づく高品質写真の選別
- 結果の表示・保存
- （将来的な機能）ネットワークドライブ対応
- （将来的な機能）新規写真の自動検出と評価

## 必要条件

- Python 3.8以上
- OpenAI APIキー

## インストール方法

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/whale.git
cd whale

# uvを使用して環境をセットアップ
uv init

# 依存パッケージのインストール
uv pip install -r requirements.txt

# 環境変数の設定
cp .env.example .env
# .envファイルを編集してOpenAI APIキーを設定
```

## 使用方法

```bash
# 基本的な使用方法
uv run src/main.py --folder /path/to/photos

# 詳細なオプションを表示
uv run src/main.py --help
```

詳細な使用方法については `USAGE.md` を参照してください。

## ライセンス

MITライセンス
