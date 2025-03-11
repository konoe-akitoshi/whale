"""
画像評価モジュール
OpenAI APIまたはOllama Visionを使用して画像を評価する機能を提供します。
並列処理を使用して大量の画像を効率的に評価します。
"""

import base64
import io
import json
import time
import requests
import concurrent.futures
from typing import List, Dict, Any, Tuple, Literal, Optional
from PIL import Image
from openai import OpenAI
from tqdm import tqdm

from src.config import (
    OPENAI_API_KEY, OLLAMA_HOST, OLLAMA_MODEL, 
    QUALITY_THRESHOLD, DEFAULT_API, logger
)

class ImageEvaluator:
    """OpenAI APIまたはOllama Visionを使用して画像を評価するクラス"""
    
    def __init__(self, api_type: Literal['openai', 'ollama'] = None, api_key: str = None, 
                 ollama_host: str = None, ollama_model: str = None):
        """
        初期化
        
        Args:
            api_type: 使用するAPI（'openai'または'ollama'）
            api_key: OpenAI APIキー（Noneの場合は環境変数から取得）
            ollama_host: OllamaのホストURL（Noneの場合は環境変数から取得）
            ollama_model: Ollamaのモデル名（Noneの場合は環境変数から取得）
        """
        self.api_type = api_type or DEFAULT_API
        
        # OpenAI API設定
        self.api_key = api_key or OPENAI_API_KEY
        if self.api_type == 'openai' and not self.api_key:
            raise ValueError("OpenAI APIキーが設定されていません")
            
        # Ollama設定
        self.ollama_host = ollama_host or OLLAMA_HOST
        self.ollama_model = ollama_model or OLLAMA_MODEL
        
        # APIクライアントの初期化
        if self.api_type == 'openai':
            self.client = OpenAI(api_key=self.api_key)
            logger.info("OpenAI APIクライアントを初期化しました")
        else:
            logger.info(f"Ollama Vision ({self.ollama_model})を使用します: {self.ollama_host}")
        
    def _resize_image(self, image: Image.Image, max_size: int = 1024) -> Image.Image:
        """
        画像を適切なサイズにリサイズする
        
        Args:
            image: PILのImageオブジェクト
            max_size: 最大サイズ（幅または高さ）
            
        Returns:
            Image.Image: リサイズされた画像
        """
        width, height = image.size
        
        # すでに十分小さい場合はリサイズしない
        if width <= max_size and height <= max_size:
            return image
            
        # アスペクト比を維持してリサイズ
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
            
        return image.resize((new_width, new_height), Image.LANCZOS)
        
    def _encode_image(self, image: Image.Image, resize: bool = True) -> str:
        """
        画像をbase64エンコードする
        
        Args:
            image: PILのImageオブジェクト
            resize: リサイズするかどうか
            
        Returns:
            str: base64エンコードされた画像データ
        """
        # 必要に応じてリサイズ
        if resize:
            image = self._resize_image(image)
            
        # RGBAモードの場合はRGBに変換（JPEGはアルファチャンネルをサポートしていないため）
        if image.mode == 'RGBA':
            # 白い背景に画像を合成
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # 3はアルファチャンネル
            image = background
        elif image.mode != 'RGB':
            # その他のモード（グレースケールなど）もRGBに変換
            image = image.convert('RGB')
            
        # 画像をJPEGフォーマットのバイトデータに変換（品質を少し下げてサイズを小さくする）
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        
        # base64エンコード
        encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded_image
        
    def _get_evaluation_prompt(self) -> str:
        """
        評価用のプロンプトを取得する
        
        Returns:
            str: 評価用のプロンプト
        """
        return """
        あなたは写真の品質を評価する専門家です。
        与えられた写真を以下の観点から1〜10の数値で評価してください：
        
        1. 構図（バランス、フレーミング、視線誘導）
        2. 露出（明るさ、コントラスト、ダイナミックレンジ）
        3. 色彩（色のバランス、彩度、色温度）
        4. 焦点（シャープネス、被写界深度、ボケ具合）
        5. 被写体（主題の明確さ、表現力、魅力）
        6. 全体的な印象（感情的なインパクト、記憶に残るか）
        
        また、総合評価（1〜10）も提供し、写真の強みと改善点を簡潔に説明してください。
        
        回答は必ず以下のJSON形式で返してください：
        {
            "composition": 数値,
            "exposure": 数値,
            "color": 数値,
            "focus": 数値,
            "subject": 数値,
            "overall_impression": 数値,
            "total_score": 数値,
            "strengths": "写真の強み",
            "improvements": "改善点",
            "description": "写真の簡潔な説明"
        }
        """
    
    def _evaluate_with_openai(self, image_info: Dict[str, Any], encoded_image: str) -> Dict[str, Any]:
        """
        OpenAI APIを使用して画像を評価する
        
        Args:
            image_info: 画像情報の辞書
            encoded_image: base64エンコードされた画像データ
            
        Returns:
            Dict[str, Any]: 評価結果を含む画像情報
        """
        try:
            # OpenAI APIを呼び出して画像を評価
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": self._get_evaluation_prompt()
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "この写真を評価してください。"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            # レスポンスからJSONを抽出
            result = response.choices[0].message.content
            
            # 評価結果を画像情報に追加
            image_info['evaluation'] = result
            
            # 総合評価スコアを取得
            evaluation_dict = json.loads(result)
            image_info['score'] = evaluation_dict.get('total_score', 0)
            image_info['is_good'] = image_info['score'] >= QUALITY_THRESHOLD
            
            return image_info
            
        except Exception as e:
            logger.error(f"OpenAI APIでの画像評価中にエラーが発生しました: {str(e)}")
            image_info['evaluation'] = None
            image_info['score'] = 0
            image_info['is_good'] = False
            return image_info
            
    def _evaluate_with_ollama(self, image_info: Dict[str, Any], encoded_image: str) -> Dict[str, Any]:
        """
        Ollama Visionを使用して画像を評価する
        
        Args:
            image_info: 画像情報の辞書
            encoded_image: base64エンコードされた画像データ
            
        Returns:
            Dict[str, Any]: 評価結果を含む画像情報
        """
        try:
            # Ollama APIエンドポイント
            url = f"{self.ollama_host}/api/generate"
            
            # リクエストデータ
            data = {
                "model": self.ollama_model,
                "prompt": f"""
                {self._get_evaluation_prompt()}
                
                この写真を評価してください:
                """,
                "images": [encoded_image],
                "stream": False,
                "format": "json"
            }
            
            # APIリクエスト
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            # レスポンスからJSONを抽出
            response_data = response.json()
            result = response_data.get('response', '')
            
            # JSONを抽出（Ollamaの出力からJSONだけを取り出す）
            try:
                # JSONの開始と終了を見つける
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = result[json_start:json_end]
                    evaluation_dict = json.loads(json_str)
                else:
                    # JSONが見つからない場合、テキスト全体をパースしてみる
                    evaluation_dict = json.loads(result)
            except json.JSONDecodeError:
                # JSONのパースに失敗した場合、デフォルト値を設定
                logger.warning(f"Ollamaの出力からJSONを抽出できませんでした: {result}")
                evaluation_dict = {
                    "composition": 5,
                    "exposure": 5,
                    "color": 5,
                    "focus": 5,
                    "subject": 5,
                    "overall_impression": 5,
                    "total_score": 5,
                    "strengths": "評価できませんでした",
                    "improvements": "評価できませんでした",
                    "description": "評価できませんでした"
                }
            
            # 評価結果を画像情報に追加
            image_info['evaluation'] = json.dumps(evaluation_dict)
            image_info['score'] = evaluation_dict.get('total_score', 0)
            image_info['is_good'] = image_info['score'] >= QUALITY_THRESHOLD
            
            return image_info
            
        except Exception as e:
            logger.error(f"Ollama Visionでの画像評価中にエラーが発生しました: {str(e)}")
            image_info['evaluation'] = None
            image_info['score'] = 0
            image_info['is_good'] = False
            return image_info
    
    def evaluate_image(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        1枚の画像を評価する
        
        Args:
            image_info: 画像情報の辞書
            
        Returns:
            Dict[str, Any]: 評価結果を含む画像情報
        """
        image = image_info['image']
        encoded_image = self._encode_image(image)
        
        # 選択されたAPIに基づいて評価メソッドを呼び出す
        if self.api_type == 'openai':
            return self._evaluate_with_openai(image_info, encoded_image)
        else:
            return self._evaluate_with_ollama(image_info, encoded_image)
            
    def _evaluate_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        バッチ単位で画像を評価する（並列処理用）
        
        Args:
            batch: 評価する画像情報のバッチ
            
        Returns:
            List[Dict[str, Any]]: 評価結果を含む画像情報のリスト
        """
        results = []
        
        # バッチ内の各画像を評価（進捗バー付き）
        for image_info in tqdm(
            batch, 
            desc=f"バッチ内評価", 
            unit="枚",
            leave=False,  # バッチが終わったら進捗バーを消す
            colour=True,
            ncols=80,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        ):
            try:
                # ファイル名を表示
                filename = image_info.get('filename', '不明なファイル')
                tqdm.write(f"評価中: {filename}")
                
                result = self.evaluate_image(image_info)
                results.append(result)
                
                # スコアを表示
                score = result.get('score', 0)
                is_good = "✓" if result.get('is_good', False) else "✗"
                tqdm.write(f"評価完了: {filename} - スコア: {score:.1f} {is_good}")
                
                # APIレート制限を考慮して少し待機
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"バッチ処理中にエラーが発生しました: {str(e)}")
                image_info['evaluation'] = None
                image_info['score'] = 0
                image_info['is_good'] = False
                results.append(image_info)
        
        return results
        
    def evaluate_images(self, images: List[Dict[str, Any]], max_workers: int = 4, batch_size: int = 10) -> List[Dict[str, Any]]:
        """
        複数の画像を並列処理で評価する
        
        Args:
            images: 画像情報のリスト
            max_workers: 並列処理の最大ワーカー数
            batch_size: 一度に処理するバッチサイズ
            
        Returns:
            List[Dict[str, Any]]: 評価結果を含む画像情報のリスト
        """
        if not images:
            return []
            
        # 画像の総数を表示
        total_images = len(images)
        logger.info(f"合計{total_images}枚の画像を評価します（並列処理: {max_workers}ワーカー）")
        
        # バッチに分割
        batches = []
        for i in range(0, len(images), batch_size):
            batches.append(images[i:i+batch_size])
            
        results = []
        
        # 並列処理でバッチを評価
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # バッチごとに並列処理を実行
            futures = [executor.submit(self._evaluate_batch, batch) for batch in batches]
            
            # 進捗状況を表示しながら結果を取得
            for future in tqdm(
                concurrent.futures.as_completed(futures), 
                total=len(futures), 
                desc="画像評価中", 
                unit="バッチ",
                colour=True,
                ncols=100,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} バッチ [{elapsed}<{remaining}, {rate_fmt}]"
            ):
                batch_results = future.result()
                results.extend(batch_results)
                
        # 結果を整理（元の順序を維持）
        sorted_results = []
        result_dict = {id(img): img for img in results}
        for img in images:
            if id(img) in result_dict:
                sorted_results.append(result_dict[id(img)])
            else:
                # 何らかの理由で結果が見つからない場合
                img['evaluation'] = None
                img['score'] = 0
                img['is_good'] = False
                sorted_results.append(img)
                
        # 良い写真の数をカウント
        good_images = [img for img in sorted_results if img.get('is_good', False)]
        logger.info(f"評価完了: 合計{len(sorted_results)}枚中{len(good_images)}枚が良い写真と判断されました")
        
        return sorted_results
