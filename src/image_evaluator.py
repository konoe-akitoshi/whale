"""
画像評価モジュール
OpenAI APIを使用して画像を評価する機能を提供します。
"""

import base64
import io
from typing import List, Dict, Any, Tuple
import time
from PIL import Image
from openai import OpenAI
from tqdm import tqdm

from src.config import OPENAI_API_KEY, QUALITY_THRESHOLD, logger

class ImageEvaluator:
    """OpenAI APIを使用して画像を評価するクラス"""
    
    def __init__(self, api_key: str = None):
        """
        初期化
        
        Args:
            api_key: OpenAI APIキー（Noneの場合は環境変数から取得）
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI APIキーが設定されていません")
            
        self.client = OpenAI(api_key=self.api_key)
        logger.info("OpenAI APIクライアントを初期化しました")
        
    def _encode_image(self, image: Image.Image) -> str:
        """
        画像をbase64エンコードする
        
        Args:
            image: PILのImageオブジェクト
            
        Returns:
            str: base64エンコードされた画像データ
        """
        # RGBAモードの場合はRGBに変換（JPEGはアルファチャンネルをサポートしていないため）
        if image.mode == 'RGBA':
            # 白い背景に画像を合成
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # 3はアルファチャンネル
            image = background
        elif image.mode != 'RGB':
            # その他のモード（グレースケールなど）もRGBに変換
            image = image.convert('RGB')
            
        # 画像をJPEGフォーマットのバイトデータに変換
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)
        
        # base64エンコード
        encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded_image
        
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
        
        try:
            # OpenAI APIを呼び出して画像を評価
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """
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
            import json
            evaluation_dict = json.loads(result)
            image_info['score'] = evaluation_dict.get('total_score', 0)
            image_info['is_good'] = image_info['score'] >= QUALITY_THRESHOLD
            
            return image_info
            
        except Exception as e:
            logger.error(f"画像評価中にエラーが発生しました: {str(e)}")
            image_info['evaluation'] = None
            image_info['score'] = 0
            image_info['is_good'] = False
            return image_info
            
    def evaluate_images(self, images: List[Dict[str, Any]], rate_limit: int = 10) -> List[Dict[str, Any]]:
        """
        複数の画像を評価する
        
        Args:
            images: 画像情報のリスト
            rate_limit: APIリクエストの1分あたりの最大数
            
        Returns:
            List[Dict[str, Any]]: 評価結果を含む画像情報のリスト
        """
        results = []
        
        # レート制限を考慮して画像を評価
        for i, image_info in enumerate(tqdm(images, desc="画像評価中")):
            # レート制限に達した場合は待機
            if i > 0 and i % rate_limit == 0:
                logger.info(f"APIレート制限のため60秒待機します（{i}/{len(images)}）")
                time.sleep(60)
                
            result = self.evaluate_image(image_info)
            results.append(result)
            
        # 良い写真の数をカウント
        good_images = [img for img in results if img.get('is_good', False)]
        logger.info(f"評価完了: 合計{len(results)}枚中{len(good_images)}枚が良い写真と判断されました")
        
        return results
