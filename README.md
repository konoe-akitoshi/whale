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
uv pip install -r whale/requirements.txt

# 環境変数の設定
cp whale/.env.example whale/.env
# .envファイルを編集してOpenAI APIキーを設定
```

## 使用方法

```bash
# 基本的な使用方法
uv run main.py --folder /path/to/photos

# 詳細なオプションを表示
uv run main.py --help
```

詳細な使用方法については `whale/USAGE.md` を参照してください。

## プロジェクト構成

```
whale/
├── .env                  - 環境変数設定ファイル（APIキーなど）
├── .env.example          - 環境変数設定のテンプレート
├── README.md             - プロジェクト概要
├── USAGE.md              - 詳細な使用方法
├── requirements.txt      - 必要なパッケージリスト
├── src/
│   ├── config.py         - 設定管理モジュール
│   ├── image_loader.py   - 画像読み込みモジュール
│   ├── image_evaluator.py - 画像評価モジュール
│   ├── result_handler.py - 結果処理モジュール
│   └── main.py           - メインプログラム
└── tests/                - テストコード用フォルダ（将来的に拡張可能）
```

## ライセンス

MITライセンス
