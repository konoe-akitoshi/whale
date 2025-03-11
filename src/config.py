"""
設定管理モジュール
環境変数から設定を読み込み、アプリケーション全体で使用できるようにします。
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('whale.log')
    ]
)
logger = logging.getLogger('whale')

# API設定
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.warning('OPENAI_API_KEYが設定されていません。')

# Ollama設定
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llava')

# 画像評価設定
QUALITY_THRESHOLD = float(os.getenv('QUALITY_THRESHOLD', '7.5'))
# デフォルトのAPI（'openai' または 'ollama'）
DEFAULT_API = os.getenv('DEFAULT_API', 'openai')

# フォルダ設定
DEFAULT_IMAGE_FOLDER = os.getenv('DEFAULT_IMAGE_FOLDER', './data/images')
RESULT_FOLDER = os.getenv('RESULT_FOLDER', './data/results')

# パスをPathオブジェクトに変換
DEFAULT_IMAGE_FOLDER_PATH = Path(DEFAULT_IMAGE_FOLDER)
RESULT_FOLDER_PATH = Path(RESULT_FOLDER)

# フォルダが存在しない場合は作成
DEFAULT_IMAGE_FOLDER_PATH.mkdir(parents=True, exist_ok=True)
RESULT_FOLDER_PATH.mkdir(parents=True, exist_ok=True)

# 監視設定
WATCH_FOLDER = os.getenv('WATCH_FOLDER', 'false').lower() == 'true'
WATCH_INTERVAL = int(os.getenv('WATCH_INTERVAL', '60'))

# サポートする画像形式
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

def get_image_folder(cmd_folder=None):
    """
    画像フォルダのパスを取得します。
    コマンドライン引数で指定されたフォルダがある場合はそれを優先し、
    なければデフォルトのフォルダを使用します。
    
    Args:
        cmd_folder: コマンドライン引数で指定されたフォルダパス
        
    Returns:
        Path: 画像フォルダのパス
    """
    if cmd_folder:
        folder_path = Path(cmd_folder)
        if not folder_path.exists():
            logger.warning(f'指定されたフォルダ {cmd_folder} が存在しません。作成します。')
            folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
    return DEFAULT_IMAGE_FOLDER_PATH
