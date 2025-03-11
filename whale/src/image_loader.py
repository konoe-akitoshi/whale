"""
画像ローダーモジュール
指定されたフォルダから画像ファイルを検索し、読み込む機能を提供します。
"""

import os
from pathlib import Path
from typing import List, Dict, Any
import logging
from PIL import Image
from tqdm import tqdm

from config import SUPPORTED_EXTENSIONS, logger

class ImageLoader:
    """画像ファイルを読み込むクラス"""
    
    def __init__(self, folder_path: Path):
        """
        初期化
        
        Args:
            folder_path: 画像ファイルを検索するフォルダのパス
        """
        self.folder_path = folder_path
        logger.info(f'画像フォルダ: {folder_path}')
        
    def get_image_files(self) -> List[Path]:
        """
        フォルダ内の画像ファイルのパスリストを取得
        
        Returns:
            List[Path]: 画像ファイルのパスリスト
        """
        if not self.folder_path.exists():
            logger.error(f'フォルダが存在しません: {self.folder_path}')
            return []
            
        image_files = []
        
        # フォルダ内のすべてのファイルを再帰的に検索
        for file_path in self.folder_path.glob('**/*'):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                image_files.append(file_path)
                
        logger.info(f'画像ファイル数: {len(image_files)}')
        return image_files
        
    def load_images(self, max_files: int = None) -> List[Dict[str, Any]]:
        """
        画像ファイルを読み込み、メタデータとともに返す
        
        Args:
            max_files: 読み込む最大ファイル数（Noneの場合は制限なし）
            
        Returns:
            List[Dict[str, Any]]: 画像情報のリスト
                各辞書には以下のキーが含まれます:
                - path: 画像ファイルのパス
                - filename: ファイル名
                - size: ファイルサイズ（バイト）
                - dimensions: 画像の寸法 (幅, 高さ)
                - format: 画像フォーマット
                - image: PILのImageオブジェクト
        """
        image_files = self.get_image_files()
        
        if max_files is not None:
            image_files = image_files[:max_files]
            
        images = []
        
        # プログレスバーを表示しながら画像を読み込む
        for file_path in tqdm(image_files, desc="画像読み込み中"):
            try:
                img = Image.open(file_path)
                
                image_info = {
                    'path': file_path,
                    'filename': file_path.name,
                    'size': file_path.stat().st_size,
                    'dimensions': img.size,
                    'format': img.format,
                    'image': img
                }
                
                images.append(image_info)
                
            except Exception as e:
                logger.error(f'画像の読み込みに失敗しました: {file_path} - {str(e)}')
                
        logger.info(f'読み込んだ画像数: {len(images)}')
        return images
