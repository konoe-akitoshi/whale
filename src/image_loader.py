"""
画像ローダーモジュール
指定されたフォルダまたはWebDAVサーバーから画像ファイルを検索し、読み込む機能を提供します。
"""

import os
import io
import tempfile
import time
import uuid
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
            colour="GREEN",  # Trueの代わりに有効な色を指定
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
            
        # URLからユーザー名とパスワードを削除（もし含まれていれば）
        cleaned_url = self.webdav_url
        if '@' in cleaned_url and '//' in cleaned_url:
            # プロトコル部分を取得
            protocol = cleaned_url.split('//')[0] + '//'
            # ユーザー名とパスワードを除いた残りの部分を取得
            remaining = cleaned_url.split('@', 1)[1]
            cleaned_url = protocol + remaining
            
        # URLの末尾に/がない場合は追加
        if not cleaned_url.endswith('/'):
            cleaned_url += '/'
            
        # リモートパスの先頭に/がない場合は追加
        if not self.remote_path.startswith('/'):
            self.remote_path = '/' + self.remote_path
            
        # リモートパスの末尾に/がない場合は追加（ディレクトリの場合）
        if not self.remote_path.endswith('/'):
            self.remote_path += '/'
            
        # URLに含まれるパスを削除（例：https://photo.akitoshi-lab.com/originals/ -> https://photo.akitoshi-lab.com/）
        base_url = cleaned_url
        url_parts = cleaned_url.split('/')
        if len(url_parts) > 3:  # プロトコル + 空文字 + ドメイン + パス
            # ドメイン部分までを取得
            base_url = url_parts[0] + '//' + url_parts[2] + '/'
            
        # URLに含まれるパスをリモートパスに追加
        if len(url_parts) > 3:
            path_in_url = '/'.join(url_parts[3:-1])  # 最後の空文字を除く
            if path_in_url:
                # リモートパスの先頭に追加
                if not self.remote_path.startswith('/' + path_in_url):
                    self.remote_path = '/' + path_in_url + self.remote_path
            
        # WebDAVクライアントの設定
        self.options = {
            'webdav_hostname': base_url,  # URLからパスを削除したベースURL
            'webdav_login': self.username,
            'webdav_password': self.password,
            'webdav_root': '',  # ルートパスは空にして、すべてのパスをremote_pathで指定
            'verify': self.verify_ssl,
            # check()メソッドを無効化
            'disable_check': True,
            # タイムアウトを設定
            'timeout': 30,
            # 再試行回数を設定
            'retry_count': 3
        }
        
        # デバッグ情報
        logger.info(f'WebDAVサーバー接続設定: URL={cleaned_url}, ユーザー名={self.username}, ルートパス={self.root_path}, SSL検証={self.verify_ssl}')
        
        try:
            # WebDAVクライアントの初期化
            self.client = WebDAVClient(self.options)
            logger.info(f'WebDAVクライアントの初期化に成功しました')
        except Exception as e:
            logger.error(f'WebDAVクライアントの初期化に失敗しました: {str(e)}')
            raise
        
        logger.info(f'WebDAVサーバー: {cleaned_url}, リモートパス: {self.remote_path}')
        
    def _download_file_method(self, remote_path: str, local_path: str) -> None:
        """
        WebDAVサーバーからファイルをダウンロードする（download_fileメソッドを使用）
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        self.client.download_file(remote_path, local_path)
        
    def _download_binary_method(self, remote_path: str, local_path: str) -> None:
        """
        WebDAVサーバーからファイルをダウンロードする（バイナリデータとして）
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        try:
            # 複数の方法を試す（成功する可能性の高い順）
            methods = [
                # 方法1: バッファを使用（フィードバックから最も成功率が高い）
                lambda: self._try_buffer_download(remote_path, local_path),
                # 方法2: 別のパスパターンでバッファを使用
                lambda: self._try_buffer_download('/' + remote_path.lstrip('/'), local_path),
                # 方法3: 直接ファイルにダウンロード
                lambda: self.client.download_file(remote_path, local_path),
                # 方法4: 別のパスパターンでダウンロード
                lambda: self.client.download_file('/' + remote_path.lstrip('/'), local_path),
            ]
            
            # 各方法を順番に試す
            for method in methods:
                try:
                    method()
                    # 成功したら終了
                    return
                except Exception:
                    # エラーは無視して次の方法を試す
                    continue
                    
            # すべての方法が失敗した場合
            raise Exception("すべてのバイナリダウンロード方法が失敗しました")
                
        except Exception as e:
            raise Exception(f'バイナリダウンロードに失敗しました: {str(e)}')
            
    def _try_resource_get(self, remote_path: str, local_path: str) -> None:
        """
        resource().get()メソッドを使用してファイルをダウンロードする
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        try:
            # resource()メソッドが存在するか確認
            if not hasattr(self.client, 'resource'):
                raise AttributeError("WebDAVクライアントにresource()メソッドがありません")
                
            # resource()メソッドを呼び出す
            resource = self.client.resource(remote_path)
            
            # get()メソッドが存在するか確認
            if not hasattr(resource, 'get'):
                raise AttributeError("resourceオブジェクトにget()メソッドがありません")
                
            # get()メソッドを呼び出す
            binary_data = resource.get()
            
            # ファイルに書き込む
            with open(local_path, 'wb') as f:
                f.write(binary_data)
                
        except Exception as e:
            raise Exception(f'resource().get()でのダウンロードに失敗しました: {str(e)}')
            
    def _try_buffer_download(self, remote_path: str, local_path: str) -> None:
        """
        バッファを使用してファイルをダウンロードする
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        try:
            # 一時ファイルを直接ダウンロード
            try:
                # download_fileメソッドを使用
                self.client.download_file(remote_path, local_path)
                return
            except Exception:
                # エラーは無視して次の方法を試す
                pass
                
            # 別の方法を試す: バイナリデータとして読み込む
            try:
                # read_binaryメソッドが存在するか確認
                if hasattr(self.client, 'read_binary'):
                    # read_binaryメソッドを使用
                    binary_data = self.client.read_binary(remote_path)
                    with open(local_path, 'wb') as f:
                        f.write(binary_data)
                    return
            except Exception:
                # エラーは無視して次の方法を試す
                pass
                
            # 別の方法を試す: requestsを使用
            try:
                import requests
                
                # WebDAVサーバーのURLを取得
                webdav_url = self.options.get('webdav_hostname', '')
                username = self.options.get('webdav_login', '')
                password = self.options.get('webdav_password', '')
                
                # URLを構築
                url = webdav_url.rstrip('/') + '/' + remote_path.lstrip('/')
                
                # Basic認証を使用してリクエスト
                response = requests.get(url, auth=(username, password), verify=self.verify_ssl)
                response.raise_for_status()
                
                # ファイルに書き込む
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                return
            except Exception:
                # エラーは無視して次の方法を試す
                pass
                
            # すべての方法が失敗した場合
            raise Exception("すべてのバッファダウンロード方法が失敗しました")
                
        except Exception as e:
            raise Exception(f'バッファを使用したダウンロードに失敗しました: {str(e)}')
            
    def _try_requests_download(self, remote_path: str, local_path: str) -> None:
        """
        requestsライブラリを使用してファイルをダウンロードする
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        try:
            import requests
            
            # WebDAVサーバーのURLを取得
            webdav_url = self.options.get('webdav_hostname', '')
            username = self.options.get('webdav_login', '')
            password = self.options.get('webdav_password', '')
            
            # 複数のURLパターンを試す
            url_patterns = [
                # パターン1: 通常のURL
                webdav_url.rstrip('/') + '/' + remote_path.lstrip('/'),
                # パターン2: originalsを含むURL
                webdav_url.rstrip('/') + '/originals/' + remote_path.lstrip('/'),
                # パターン3: originalsを含まないURL
                webdav_url.rstrip('/') + '/' + remote_path.replace('/originals', '').lstrip('/'),
                # パターン4: smb/Photoを含まないURL
                webdav_url.rstrip('/') + '/' + remote_path.replace('/smb/Photo', '').lstrip('/'),
                # パターン5: originalsとsmb/Photoの両方を含まないURL
                webdav_url.rstrip('/') + '/' + remote_path.replace('/originals', '').replace('/smb/Photo', '').lstrip('/'),
                # パターン6: ファイル名のみのURL
                webdav_url.rstrip('/') + '/' + os.path.basename(remote_path),
                # パターン7: 年月日フォルダを含むURL
                webdav_url.rstrip('/') + '/2025/2025-01-01/' + os.path.basename(remote_path),
                # パターン8: 年フォルダのみを含むURL
                webdav_url.rstrip('/') + '/2025/' + os.path.basename(remote_path),
            ]
            
            # 各URLパターンを順番に試す
            for i, url in enumerate(url_patterns):
                try:
                    # Basic認証を使用してリクエスト
                    response = requests.get(url, auth=(username, password), verify=self.verify_ssl, timeout=30)
                    response.raise_for_status()
                    
                    # ファイルに書き込む
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                        
                    # 成功したURLパターンのみログに記録
                    logger.info(f'ダウンロードに成功しました: {os.path.basename(remote_path)}')
                    return
                except Exception:
                    # エラーは無視して次のパターンを試す
                    continue
                    
            # すべてのURLパターンが失敗した場合
            raise Exception("すべてのURLパターンが失敗しました")
                
        except Exception as e:
            raise Exception(f'requestsを使用したダウンロードに失敗しました: {str(e)}')
        
    def _list_directory(self, path: str, recursive: bool = True) -> List[Dict[str, Any]]:
        """
        WebDAVサーバー上のディレクトリをリストアップする
        
        Args:
            path: リストアップするディレクトリのパス
            recursive: 再帰的にリストアップするかどうか
            
        Returns:
            List[Dict[str, Any]]: ファイル情報のリスト
        """
        try:
            # パスの正規化
            if not path.startswith('/'):
                path = '/' + path
                
            # 複数の方法を試す
            methods = [
                # 方法1: 通常のlist
                lambda: self.client.list(path, get_info=True),
                # 方法2: 単純なlist
                lambda: [{'path': os.path.join(path, f).replace('\\', '/'), 'isdir': f.endswith('/')} 
                         for f in self.client.list(path)],
                # 方法3: ルートからの相対パス
                lambda: self.client.list('/' + path.lstrip('/'), get_info=True),
                # 方法4: 親ディレクトリからのリスト
                lambda: self._list_parent_directory(path)
            ]
            
            # 各方法を順番に試す
            for i, method in enumerate(methods):
                try:
                    files = method()
                    if files:  # 空でない結果が得られたら成功
                        logger.info(f'方法{i+1}でリスト取得に成功しました: {path}')
                        return files
                except Exception:
                    # エラーは無視して次の方法を試す
                    continue
                    
            # すべての方法が失敗した場合
            logger.debug(f'すべての方法でリスト取得に失敗しました: {path}')
            return []
            
        except Exception as e:
            logger.debug(f'ディレクトリのリスト取得に失敗しました: {path} - {str(e)}')
            return []
            
    def _list_parent_directory(self, path: str) -> List[Dict[str, Any]]:
        """
        親ディレクトリをリストアップし、指定されたパスのファイルのみをフィルタリングする
        
        Args:
            path: 対象のパス
            
        Returns:
            List[Dict[str, Any]]: ファイル情報のリスト
        """
        # 親ディレクトリのパスを取得
        parent_path = os.path.dirname(path.rstrip('/'))
        if not parent_path:
            parent_path = '/'
            
        try:
            # 親ディレクトリのリストを取得
            parent_files = self.client.list(parent_path, get_info=True)
            
            # 対象のパスのファイルのみをフィルタリング
            target_name = os.path.basename(path.rstrip('/'))
            filtered_files = []
            
            for file_info in parent_files:
                if isinstance(file_info, dict):
                    file_path = file_info.get('path', '')
                    if file_path.endswith(target_name) or file_path.endswith(target_name + '/'):
                        filtered_files.append(file_info)
                        
            return filtered_files
        except Exception:
            # エラーは無視して空のリストを返す
            return []
    
    def get_image_files(self) -> List[str]:
        """
        WebDAVサーバー上の画像ファイルのパスリストを取得（再帰的）
        
        Returns:
            List[str]: 画像ファイルのパスリスト
        """
        try:
            # 再帰的にファイルを検索する関数
            def search_recursively(current_path: str) -> List[str]:
                result = []
                
                # 現在のディレクトリのファイルとフォルダをリストアップ
                items = self._list_directory(current_path)
                
                for item in items:
                    # 辞書の場合
                    if isinstance(item, dict):
                        item_path = item.get('path', '')
                        is_dir = item.get('isdir', False)
                    # 文字列の場合
                    elif isinstance(item, str):
                        item_path = os.path.join(current_path, item)
                        is_dir = item.endswith('/')
                    else:
                        continue
                    
                    # ディレクトリの場合は再帰的に検索
                    if is_dir:
                        # パスの末尾に/がない場合は追加
                        if not item_path.endswith('/'):
                            item_path += '/'
                        # 再帰的に検索
                        sub_results = search_recursively(item_path)
                        result.extend(sub_results)
                    else:
                        # ファイルの場合は拡張子をチェック
                        _, ext = os.path.splitext(item_path)
                        if ext.lower() in SUPPORTED_EXTENSIONS:
                            result.append(item_path)
                
                return result
            
            # 再帰的に検索を開始
            logger.info(f'WebDAVサーバー上のファイルを再帰的に検索します: {self.remote_path}')
            image_files = search_recursively(self.remote_path)
            
            logger.info(f'WebDAVサーバー上の画像ファイル数: {len(image_files)}')
            return image_files
            
        except Exception as e:
            logger.error(f'WebDAVサーバーからファイルリストの取得に失敗しました: {str(e)}')
            return []
            
    def load_images(self, max_files: int = None, batch_size: int = 100) -> List[Dict[str, Any]]:
        """
        WebDAVサーバーから画像ファイルを読み込み、メタデータとともに返す
        
        Args:
            max_files: 読み込む最大ファイル数（Noneの場合は制限なし）
            batch_size: 一度に処理するファイル数のバッチサイズ
            
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
        # multiprocessingのリソーストラッカーを無効化（セマフォリーク対策）
        try:
            import multiprocessing as mp
            # リソーストラッカーを無効化（環境変数を設定）
            os.environ["PYTHONMULTIPROCESSING"] = "1"
            # すでに起動している場合は停止
            if hasattr(mp, 'resource_tracker') and hasattr(mp.resource_tracker, '_resource_tracker'):
                if mp.resource_tracker._resource_tracker is not None:
                    try:
                        mp.resource_tracker._resource_tracker._stop = True
                    except Exception:
                        pass
        except Exception:
            pass
            
        image_files = self.get_image_files()
        
        if max_files is not None:
            image_files = image_files[:max_files]
            
        images = []
        total_files = len(image_files)
        
        # バッチ処理のためにファイルリストを分割
        batches = []
        for i in range(0, total_files, batch_size):
            batches.append(image_files[i:i+batch_size])
            
        logger.info(f'WebDAVサーバーから画像を読み込みます: 合計{total_files}枚、{len(batches)}バッチ')
        
        # 一時ディレクトリを作成（すべてのバッチで共有）
        temp_dir = tempfile.mkdtemp()
        try:
            # バッチごとに処理
            for batch_index, batch_files in enumerate(batches):
                logger.info(f'バッチ {batch_index+1}/{len(batches)} を処理中 ({len(batch_files)}枚)')
                
                # プログレスバーを表示しながら画像を読み込む
                for file_path in tqdm(
                    batch_files, 
                    desc=f"WebDAVから画像読み込み中", 
                    unit="枚",
                    colour="GREEN",
                    ncols=100,
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
                ):
                    try:
                        # ファイル名を取得
                        filename = os.path.basename(file_path)
                        
                        # 一時ファイルパスを作成（ユニークな名前を使用）
                        temp_file = os.path.join(temp_dir, f"{int(time.time() * 1000)}_{filename}")
                        
                        # WebDAVサーバーからファイルをダウンロード
                        try:
                            # フィードバックから、方法2が成功していることがわかったので、最初に試す
                            try:
                                self._download_binary_method(file_path, temp_file)
                                with Image.open(temp_file) as img:
                                    # 画像情報を取得
                                    file_size = os.path.getsize(temp_file)
                                    dimensions = img.size
                                    format_name = img.format
                                    # 画像をコピーして保持（元のファイルハンドルは閉じる）
                                    img_copy = img.copy()
                                logger.info(f'ダウンロードに成功しました: {file_path}')
                            except Exception as e:
                                logger.warning(f'バイナリダウンロードに失敗しました: {str(e)}')
                                # 代替方法を試す
                                self._try_alternative_download(file_path, temp_file)
                                with Image.open(temp_file) as img:
                                    # 画像情報を取得
                                    file_size = os.path.getsize(temp_file)
                                    dimensions = img.size
                                    format_name = img.format
                                    # 画像をコピーして保持（元のファイルハンドルは閉じる）
                                    img_copy = img.copy()
                                
                        except Exception as download_error:
                            logger.error(f'ファイルのダウンロードに失敗しました: {file_path} - {str(download_error)}')
                            continue  # 次のファイルへ
                        
                        # 一時ファイルを明示的に削除（ファイルハンドルを閉じた後）
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass  # 削除に失敗しても続行
                        
                        image_info = {
                            'path': file_path,
                            'filename': filename,
                            'size': file_size,
                            'dimensions': dimensions,
                            'format': format_name,
                            'image': img_copy
                        }
                        
                        images.append(image_info)
                        
                    except Exception as e:
                        logger.error(f'WebDAVサーバーからの画像の読み込みに失敗しました: {file_path} - {str(e)}')
                
                # バッチ処理後にガベージコレクションを実行
                import gc
                gc.collect()
                
        finally:
            # 一時ディレクトリを明示的に削除
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
                    
        logger.info(f'WebDAVサーバーから読み込んだ画像数: {len(images)}')
        return images
        
    def _try_alternative_download(self, remote_path: str, local_path: str) -> None:
        """
        代替ダウンロード方法を試す
        
        Args:
            remote_path: リモートファイルのパス
            local_path: ローカルファイルのパス
        """
        # 最も成功する可能性の高い方法を優先的に試す
        download_methods = [
            # requestsを使用した方法
            lambda: self._try_requests_download(remote_path, local_path),
            # パスを修正してバイナリダウンロード
            lambda: self._download_binary_method('/' + remote_path.lstrip('/'), local_path),
            # ファイル名のみを使用
            lambda: self._try_requests_download('/' + os.path.basename(remote_path), local_path),
            # 年月日フォルダを含むパス
            lambda: self._try_requests_download('/2025/2025-01-01/' + os.path.basename(remote_path), local_path),
        ]
        
        # 各方法を順番に試す
        for method in download_methods:
            try:
                method()
                return  # 成功したら終了
            except Exception:
                continue  # 次の方法を試す
                
        # すべての方法が失敗した場合
        raise Exception("すべての代替ダウンロード方法が失敗しました")
