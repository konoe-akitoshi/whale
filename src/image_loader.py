"""
画像ローダーモジュール
指定されたフォルダまたはWebDAVサーバーから画像ファイルを検索し、読み込む機能を提供します。
"""

import os
import io
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging
from PIL import Image
from tqdm import tqdm

try:
    from webdav3.client import Client as WebDAVClient
    WEBDAV_AVAILABLE = True
except ImportError:
    WEBDAV_AVAILABLE = False
    
from src.config import (
    SUPPORTED_EXTENSIONS, WEBDAV_URL, WEBDAV_USERNAME, 
    WEBDAV_PASSWORD, WEBDAV_ROOT, WEBDAV_VERIFY_SSL, logger
)

class ImageLoader:
    """ローカルの画像ファイルを読み込むクラス"""
    
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
        for file_path in tqdm(
            image_files, 
            desc="画像読み込み中", 
            unit="枚",
            colour=True,
            ncols=100,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
        ):
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


class WebDAVImageLoader:
    """WebDAVサーバーから画像ファイルを読み込むクラス"""
    
    def __init__(self, webdav_url: str = None, username: str = None, password: str = None, 
                 root_path: str = None, verify_ssl: bool = True, remote_path: str = '/'):
        """
        初期化
        
        Args:
            webdav_url: WebDAVサーバーのURL
            username: WebDAVサーバーのユーザー名
            password: WebDAVサーバーのパスワード
            root_path: WebDAVサーバーのルートパス
            verify_ssl: SSL証明書を検証するかどうか
            remote_path: 画像を検索するリモートパス
        """
        if not WEBDAV_AVAILABLE:
            raise ImportError("webdavclient3パッケージがインストールされていません。pip install webdavclient3 を実行してください。")
            
        self.webdav_url = webdav_url or WEBDAV_URL
        self.username = username or WEBDAV_USERNAME
        self.password = password or WEBDAV_PASSWORD
        self.root_path = root_path or WEBDAV_ROOT
        self.verify_ssl = verify_ssl if verify_ssl is not None else WEBDAV_VERIFY_SSL
        self.remote_path = remote_path
        
        if not self.webdav_url:
            raise ValueError("WebDAV URLが設定されていません。")
            
        # WebDAVクライアントの設定
        self.options = {
            'webdav_hostname': self.webdav_url,
            'webdav_login': self.username,
            'webdav_password': self.password,
            'webdav_root': self.root_path,
            'verify': self.verify_ssl
        }
        
        # WebDAVクライアントの初期化
        self.client = WebDAVClient(self.options)
        
        logger.info(f'WebDAVサーバー: {self.webdav_url}, リモートパス: {self.remote_path}')
        
    def get_image_files(self) -> List[str]:
        """
        WebDAVサーバー上の画像ファイルのパスリストを取得
        
        Returns:
            List[str]: 画像ファイルのパスリスト
        """
        try:
            # リモートパスが存在するか確認
            if not self.client.check(self.remote_path):
                logger.error(f'リモートパスが存在しません: {self.remote_path}')
                return []
                
            # リモートパス内のファイルを再帰的に取得
            files = self.client.list(self.remote_path, get_info=True)
            
            # ディレクトリを除外し、サポートされている画像形式のみを抽出
            image_files = []
            for file_info in files:
                if file_info.get('isdir', True):
                    continue
                    
                file_path = file_info.get('path', '')
                _, ext = os.path.splitext(file_path)
                if ext.lower() in SUPPORTED_EXTENSIONS:
                    image_files.append(file_path)
                    
            logger.info(f'WebDAVサーバー上の画像ファイル数: {len(image_files)}')
            return image_files
            
        except Exception as e:
            logger.error(f'WebDAVサーバーからファイルリストの取得に失敗しました: {str(e)}')
            return []
            
    def load_images(self, max_files: int = None) -> List[Dict[str, Any]]:
        """
        WebDAVサーバーから画像ファイルを読み込み、メタデータとともに返す
        
        Args:
            max_files: 読み込む最大ファイル数（Noneの場合は制限なし）
            
        Returns:
            List[Dict[str, Any]]: 画像情報のリスト
                各辞書には以下のキーが含まれます:
                - path: 画像ファイルのパス（WebDAVサーバー上のパス）
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
        
        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory() as temp_dir:
            # プログレスバーを表示しながら画像を読み込む
            for file_path in tqdm(
                image_files, 
                desc="WebDAVから画像読み込み中", 
                unit="枚",
                colour=True,
                ncols=100,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            ):
                try:
                    # ファイル名を取得
                    filename = os.path.basename(file_path)
                    
                    # 一時ファイルパスを作成
                    temp_file = os.path.join(temp_dir, filename)
                    
                    # WebDAVサーバーからファイルをダウンロード
                    buffer = io.BytesIO()
                    self.client.download_to(file_path, buffer)
                    buffer.seek(0)
                    
                    # PILで画像を開く
                    img = Image.open(buffer)
                    
                    # ファイルサイズを取得
                    buffer.seek(0, io.SEEK_END)
                    file_size = buffer.tell()
                    
                    image_info = {
                        'path': file_path,
                        'filename': filename,
                        'size': file_size,
                        'dimensions': img.size,
                        'format': img.format,
                        'image': img
                    }
                    
                    images.append(image_info)
                    
                except Exception as e:
                    logger.error(f'WebDAVサーバーからの画像の読み込みに失敗しました: {file_path} - {str(e)}')
                    
        logger.info(f'WebDAVサーバーから読み込んだ画像数: {len(images)}')
        return images
