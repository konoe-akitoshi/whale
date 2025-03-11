#!/usr/bin/env python3
"""
写真評価ツール（Whale）のメインモジュール
OpenAI APIを使用して、フォルダ内の写真を自動的に評価し、高品質な写真を選別するツール。
"""

import os
import sys
import argparse
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 自作モジュールのインポート
from src.config import get_image_folder, WATCH_FOLDER, WATCH_INTERVAL, logger
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
        description='OpenAI APIを使用して写真を評価し、高品質な写真を選別するツール'
    )
    
    parser.add_argument(
        '--folder', '-f',
        type=str,
        help='評価する写真が含まれるフォルダのパス'
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
    
    return parser.parse_args()

def evaluate_photos(folder_path: Path, max_files: Optional[int] = None) -> Dict[str, Any]:
    """
    指定されたフォルダ内の写真を評価する
    
    Args:
        folder_path: 写真フォルダのパス
        max_files: 評価する最大ファイル数
        
    Returns:
        Dict[str, Any]: 評価結果の概要
    """
    logger.info("写真評価を開始します")
    
    # 画像の読み込み
    loader = ImageLoader(folder_path)
    images = loader.load_images(max_files)
    
    if not images:
        logger.info("評価する画像がありません。画像を data/images フォルダに配置するか、--folder オプションで画像フォルダを指定してください。")
        return {"status": "info", "message": "評価する画像がありません。画像を配置してください。"}
    
    # 画像の評価
    try:
        evaluator = ImageEvaluator()
        evaluated_images = evaluator.evaluate_images(images)
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

def main():
    """メイン関数"""
    # コマンドライン引数の解析
    args = parse_arguments()
    
    # 画像フォルダの取得
    folder_path = get_image_folder(args.folder)
    
    # 監視モードが指定されている場合
    if args.watch or WATCH_FOLDER:
        watch_folder(folder_path, args.interval, args.max)
    else:
        # 通常モード: 一度だけ評価を実行
        results = evaluate_photos(folder_path, args.max)
        
        if results.get("status") == "success":
            print("\n=== 評価結果 ===")
            print(f"合計写真数: {results.get('total_images', 0)}")
            print(f"良い写真数: {results.get('good_images', 0)}")
            print(f"結果フォルダ: {results.get('result_folder', '')}")
            print(f"良い写真フォルダ: {results.get('good_photos_folder', '')}")
            print(f"サマリーレポート: {results.get('summary_report', '')}")
        else:
            print(f"\nエラー: {results.get('message', '不明なエラー')}")

if __name__ == "__main__":
    main()
