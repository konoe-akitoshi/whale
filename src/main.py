#!/usr/bin/env python3
"""
写真評価ツール（Whale）のメインモジュール
OpenAI APIを使用して、フォルダ内の写真を自動的に評価し、高品質な写真を選別するツール。
"""

# 環境変数を設定（セマフォリーク対策）
import os
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
os.environ["PYTHONMULTIPROCESSING"] = "1"

# 警告フィルターを設定（セマフォリーク警告を無視）
import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be .* leaked semaphore objects")

# multiprocessingのスタートメソッドを設定
import multiprocessing
try:
    # macOSでは'spawn'を使用
    if hasattr(multiprocessing, 'set_start_method'):
        multiprocessing.set_start_method('spawn', force=True)
except Exception:
    pass

# リソーストラッカーを無効化
try:
    if hasattr(multiprocessing, 'resource_tracker'):
        multiprocessing.resource_tracker._resource_tracker = None
except Exception:
    pass

import sys
import argparse
import time
import atexit
from pathlib import Path
from typing import Dict, Any, Optional

# 自作モジュールのインポート
from src.config import (
    get_image_folder, WATCH_FOLDER, WATCH_INTERVAL, 
    DEFAULT_API, OLLAMA_HOST, OLLAMA_MODEL, logger
)
from src.image_loader import ImageLoader
from src.image_evaluator import ImageEvaluator
from src.result_handler import ResultHandler

# ファイル監視用（将来的な機能）
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdogパッケージがインストールされていないため、フォルダ監視機能は無効です")

def parse_arguments():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(
        description='OpenAI APIまたはOllama Visionを使用して写真を評価し、高品質な写真を選別するツール'
    )
    
    # 入力ソース（ローカルフォルダまたはWebDAV）
    source_group = parser.add_mutually_exclusive_group()
    
    source_group.add_argument(
        '--folder', '-f',
        type=str,
        help='評価する写真が含まれるローカルフォルダのパス'
    )
    
    source_group.add_argument(
        '--webdav', '-d',
        type=str,
        help='WebDAVサーバー上の画像フォルダのパス'
    )
    
    parser.add_argument(
        '--max', '-m',
        type=int,
        default=None,
        help='評価する最大写真数（デフォルト: 制限なし）'
    )
    
    parser.add_argument(
        '--watch', '-w',
        action='store_true',
        help='フォルダを監視し、新しい写真を自動的に評価する（将来的な機能）'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=WATCH_INTERVAL,
        help=f'監視モード時のチェック間隔（秒）（デフォルト: {WATCH_INTERVAL}秒）'
    )
    
    # 並列処理のオプションを追加
    parser.add_argument(
        '--workers', '-W',
        type=int,
        default=4,
        help='並列処理の最大ワーカー数（デフォルト: 4）'
    )
    
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=10,
        help='一度に処理するバッチサイズ（デフォルト: 10）'
    )
    
    parser.add_argument(
        '--resize', '-r',
        type=int,
        default=1024,
        help='画像の最大サイズ（幅または高さ）（デフォルト: 1024ピクセル）'
    )
    
    # API選択オプション
    parser.add_argument(
        '--api', '-a',
        type=str,
        choices=['openai', 'ollama'],
        default=DEFAULT_API,
        help='使用するAPI（openai または ollama）（デフォルト: 環境変数またはopenai）'
    )
    
    parser.add_argument(
        '--ollama-model', '-O',
        type=str,
        default=OLLAMA_MODEL,
        help=f'使用するOllamaモデル（デフォルト: {OLLAMA_MODEL}）'
    )
    
    parser.add_argument(
        '--ollama-host', '-H',
        type=str,
        default=OLLAMA_HOST,
        help=f'OllamaのホストURL（デフォルト: {OLLAMA_HOST}）'
    )
    
    return parser.parse_args()

def evaluate_photos(
    folder_path: Path, 
    max_files: Optional[int] = None,
    max_workers: int = 4,
    batch_size: int = 10,
    resize_max: int = 1024,
    api_type: str = 'openai',
    ollama_host: str = None,
    ollama_model: str = None
) -> Dict[str, Any]:
    """
    指定されたフォルダ内の写真を評価する
    
    Args:
        folder_path: 写真フォルダのパス
        max_files: 評価する最大ファイル数
        max_workers: 並列処理の最大ワーカー数
        batch_size: 一度に処理するバッチサイズ
        resize_max: 画像の最大サイズ（幅または高さ）
        api_type: 使用するAPI（'openai'または'ollama'）
        ollama_host: OllamaのホストURL
        ollama_model: Ollamaのモデル名
        
    Returns:
        Dict[str, Any]: 評価結果の概要
    """
    api_name = "OpenAI API" if api_type == 'openai' else f"Ollama Vision ({ollama_model})"
    logger.info(f"写真評価を開始します（API: {api_name}、並列処理: {max_workers}ワーカー、バッチサイズ: {batch_size}）")
    
    # 画像の読み込み
    loader = ImageLoader(folder_path)
    images = loader.load_images(max_files)
    
    if not images:
        logger.info("評価する画像がありません。画像を data/images フォルダに配置するか、--folder オプションで画像フォルダを指定してください。")
        return {"status": "info", "message": "評価する画像がありません。画像を配置してください。"}
    
    # 画像の評価
    try:
        # 評価器の初期化（APIタイプを指定）
        evaluator = ImageEvaluator(
            api_type=api_type,
            ollama_host=ollama_host,
            ollama_model=ollama_model
        )
        
        # リサイズの最大サイズを設定（オリジナルの関数を保存）
        original_resize = evaluator._resize_image
        evaluator._resize_image = lambda img, max_size=None: original_resize(img, resize_max)
        
        # 並列処理で評価
        evaluated_images = evaluator.evaluate_images(images, max_workers=max_workers, batch_size=batch_size)
    except Exception as e:
        logger.error(f"画像評価中にエラーが発生しました: {str(e)}")
        return {"status": "error", "message": f"画像評価中にエラーが発生しました: {str(e)}"}
    
    # 結果の保存
    result_handler = ResultHandler()
    results = result_handler.save_results(evaluated_images)
    
    logger.info("写真評価が完了しました")
    return results

# 将来的な機能: フォルダ監視クラス
class PhotoWatcher(FileSystemEventHandler):
    """新しい写真ファイルを監視するクラス"""
    
    def __init__(self, folder_path: Path, max_files: Optional[int] = None):
        """
        初期化
        
        Args:
            folder_path: 監視するフォルダのパス
            max_files: 一度に評価する最大ファイル数
        """
        self.folder_path = folder_path
        self.max_files = max_files
        self.processed_files = set()
        
    def on_created(self, event):
        """ファイル作成イベントのハンドラ"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return
            
        if str(file_path) in self.processed_files:
            return
            
        logger.info(f"新しい写真を検出しました: {file_path}")
        self.processed_files.add(str(file_path))
        
        # 新しい写真を評価
        evaluate_photos(self.folder_path, self.max_files)

def watch_folder(folder_path: Path, interval: int, max_files: Optional[int] = None):
    """
    フォルダを監視し、新しい写真を自動的に評価する（将来的な機能）
    
    Args:
        folder_path: 監視するフォルダのパス
        interval: チェック間隔（秒）
        max_files: 一度に評価する最大ファイル数
    """
    if not WATCHDOG_AVAILABLE:
        logger.error("watchdogパッケージがインストールされていないため、フォルダ監視機能は使用できません")
        return
        
    logger.info(f"フォルダ監視を開始します: {folder_path}")
    
    event_handler = PhotoWatcher(folder_path, max_files)
    observer = Observer()
    observer.schedule(event_handler, str(folder_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(interval)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("フォルダ監視を停止しました")
    
    observer.join()

def evaluate_webdav_photos(
    remote_path: str,
    max_files: Optional[int] = None,
    max_workers: int = 4,
    batch_size: int = 10,
    resize_max: int = 1024,
    api_type: str = 'openai',
    ollama_host: str = None,
    ollama_model: str = None
) -> Dict[str, Any]:
    """
    WebDAVサーバー上の写真を評価する
    
    Args:
        remote_path: WebDAVサーバー上の画像フォルダのパス
        max_files: 評価する最大ファイル数
        max_workers: 並列処理の最大ワーカー数
        batch_size: 一度に処理するバッチサイズ
        resize_max: 画像の最大サイズ（幅または高さ）
        api_type: 使用するAPI（'openai'または'ollama'）
        ollama_host: OllamaのホストURL
        ollama_model: Ollamaのモデル名
        
    Returns:
        Dict[str, Any]: 評価結果の概要
    """
    from src.image_loader import WebDAVImageLoader, WEBDAV_AVAILABLE
    
    if not WEBDAV_AVAILABLE:
        return {
            "status": "error", 
            "message": "webdavclient3パッケージがインストールされていません。pip install webdavclient3 を実行してください。"
        }
    
    api_name = "OpenAI API" if api_type == 'openai' else f"Ollama Vision ({ollama_model})"
    logger.info(f"WebDAVサーバーから写真評価を開始します（API: {api_name}、並列処理: {max_workers}ワーカー、バッチサイズ: {batch_size}）")
    
    try:
        # WebDAVから画像を読み込む
        loader = WebDAVImageLoader(remote_path=remote_path)
        images = loader.load_images(max_files)
        
        if not images:
            logger.info(f"WebDAVサーバー上に評価する画像がありません: {remote_path}")
            return {"status": "info", "message": "WebDAVサーバー上に評価する画像がありません。"}
        
        # 画像の評価
        evaluator = ImageEvaluator(
            api_type=api_type,
            ollama_host=ollama_host,
            ollama_model=ollama_model
        )
        
        # リサイズの最大サイズを設定（オリジナルの関数を保存）
        original_resize = evaluator._resize_image
        evaluator._resize_image = lambda img, max_size=None: original_resize(img, resize_max)
        
        # 並列処理で評価
        evaluated_images = evaluator.evaluate_images(images, max_workers=max_workers, batch_size=batch_size)
        
        # 結果の保存
        result_handler = ResultHandler()
        results = result_handler.save_results(evaluated_images)
        
        logger.info("WebDAVサーバーからの写真評価が完了しました")
        return results
        
    except Exception as e:
        logger.error(f"WebDAVサーバーからの画像評価中にエラーが発生しました: {str(e)}")
        return {"status": "error", "message": f"WebDAVサーバーからの画像評価中にエラーが発生しました: {str(e)}"}

def disable_mp_resource_tracker():
    """multiprocessingのリソーストラッカーを無効化する（セマフォリーク対策）"""
    try:
        # macOSでのフォークセーフティを無効化
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        
        # multiprocessingのリソーストラッカーを無効化
        import multiprocessing as mp
        # リソーストラッカーを無効化（環境変数を設定）
        os.environ["PYTHONMULTIPROCESSING"] = "1"
        
        # すでに起動している場合は停止
        if hasattr(mp, 'resource_tracker') and hasattr(mp.resource_tracker, '_resource_tracker'):
            if mp.resource_tracker._resource_tracker is not None:
                try:
                    mp.resource_tracker._resource_tracker._stop = True
                    # 明示的にリソーストラッカーを停止
                    mp.resource_tracker._resource_tracker.join()
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"リソーストラッカーの無効化に失敗しました: {str(e)}")

def cleanup_resources():
    """プログラム終了時にリソースをクリーンアップする"""
    try:
        # 一時ディレクトリをクリーンアップ
        import tempfile
        import shutil
        temp_dir = tempfile.gettempdir()
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            try:
                if os.path.isdir(item_path) and item.startswith('tmp'):
                    shutil.rmtree(item_path, ignore_errors=True)
            except Exception:
                pass
                
        # ガベージコレクションを実行
        import gc
        gc.collect()
        
        # multiprocessingのリソースをクリーンアップ
        try:
            import multiprocessing as mp
            if hasattr(mp, 'util') and hasattr(mp.util, '_cleanup'):
                mp.util._cleanup()
        except Exception:
            pass
            
    except Exception as e:
        logger.debug(f"リソースのクリーンアップに失敗しました: {str(e)}")

def main():
    """メイン関数"""
    # multiprocessingのリソーストラッカーを無効化
    disable_mp_resource_tracker()
    
    try:
        # コマンドライン引数の解析
        args = parse_arguments()
        
        # WebDAVモードが指定されている場合
        if args.webdav:
            results = evaluate_webdav_photos(
                args.webdav,
                args.max,
                max_workers=args.workers,
                batch_size=args.batch_size,
                resize_max=args.resize,
                api_type=args.api,
                ollama_host=args.ollama_host,
                ollama_model=args.ollama_model
            )
        else:
            # ローカルフォルダモード
            # 画像フォルダの取得
            folder_path = get_image_folder(args.folder)
            
            # 監視モードが指定されている場合
            if args.watch or WATCH_FOLDER:
                watch_folder(folder_path, args.interval, args.max)
                return  # 監視モードの場合は結果表示をスキップ
            else:
                # 通常モード: 一度だけ評価を実行
                results = evaluate_photos(
                    folder_path, 
                    args.max,
                    max_workers=args.workers,
                    batch_size=args.batch_size,
                    resize_max=args.resize,
                    api_type=args.api,
                    ollama_host=args.ollama_host,
                    ollama_model=args.ollama_model
                )
        
        # 結果の表示（WebDAVモードとローカルフォルダモードの両方で使用）
        if results.get("status") == "success":
            print("\n=== 評価結果 ===")
            print(f"合計写真数: {results.get('total_images', 0)}")
            print(f"良い写真数: {results.get('good_images', 0)}")
            print(f"結果フォルダ: {results.get('result_folder', '')}")
            print(f"良い写真フォルダ: {results.get('good_photos_folder', '')}")
            print(f"サマリーレポート: {results.get('summary_report', '')}")
        else:
            print(f"\nエラー: {results.get('message', '不明なエラー')}")
            
    finally:
        # プログラム終了時にリソースをクリーンアップ
        cleanup_resources()

if __name__ == "__main__":
    main()
