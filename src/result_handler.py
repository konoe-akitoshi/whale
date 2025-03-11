"""
結果処理モジュール
評価結果を処理し、レポートを生成・保存する機能を提供します。
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import csv
from PIL import Image

from src.config import RESULT_FOLDER_PATH, QUALITY_THRESHOLD, logger

class ResultHandler:
    """評価結果を処理するクラス"""
    
    def __init__(self, result_folder: Path = None):
        """
        初期化
        
        Args:
            result_folder: 結果を保存するフォルダのパス（Noneの場合は設定から取得）
        """
        self.result_folder = result_folder or RESULT_FOLDER_PATH
        self.result_folder.mkdir(parents=True, exist_ok=True)
        
        # 実行時のタイムスタンプを使用してユニークなフォルダを作成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_folder = self.result_folder / f"run_{timestamp}"
        self.run_folder.mkdir(parents=True, exist_ok=True)
        
        # 良い写真を保存するフォルダ
        self.good_photos_folder = self.run_folder / "good_photos"
        self.good_photos_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"結果保存フォルダ: {self.run_folder}")
        
    def save_results(self, evaluated_images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        評価結果を保存する
        
        Args:
            evaluated_images: 評価済みの画像情報リスト
            
        Returns:
            Dict[str, Any]: 保存結果の概要
        """
        if not evaluated_images:
            logger.warning("保存する評価結果がありません")
            return {"status": "error", "message": "評価結果がありません"}
            
        # 良い写真をフィルタリング
        good_images = [img for img in evaluated_images if img.get('is_good', False)]
        
        # 評価結果をJSONとして保存
        json_path = self.run_folder / "evaluation_results.json"
        self._save_json_results(evaluated_images, json_path)
        
        # 評価結果をCSVとして保存
        csv_path = self.run_folder / "evaluation_results.csv"
        self._save_csv_results(evaluated_images, csv_path)
        
        # 良い写真をコピー
        self._copy_good_photos(good_images)
        
        # サマリーレポートを生成
        summary_path = self.run_folder / "summary.txt"
        self._generate_summary(evaluated_images, summary_path)
        
        return {
            "status": "success",
            "total_images": len(evaluated_images),
            "good_images": len(good_images),
            "result_folder": str(self.run_folder),
            "good_photos_folder": str(self.good_photos_folder),
            "json_report": str(json_path),
            "csv_report": str(csv_path),
            "summary_report": str(summary_path)
        }
        
    def _save_json_results(self, evaluated_images: List[Dict[str, Any]], json_path: Path) -> None:
        """
        評価結果をJSONとして保存
        
        Args:
            evaluated_images: 評価済みの画像情報リスト
            json_path: 保存先のパス
        """
        # PILのImageオブジェクトはシリアライズできないので除外
        serializable_results = []
        for img_info in evaluated_images:
            result = {k: v for k, v in img_info.items() if k != 'image'}
            # Pathオブジェクトを文字列に変換
            result['path'] = str(result['path'])
            serializable_results.append(result)
            
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
            
        logger.info(f"JSON結果を保存しました: {json_path}")
        
    def _save_csv_results(self, evaluated_images: List[Dict[str, Any]], csv_path: Path) -> None:
        """
        評価結果をCSVとして保存
        
        Args:
            evaluated_images: 評価済みの画像情報リスト
            csv_path: 保存先のパス
        """
        if not evaluated_images:
            return
            
        # CSVのヘッダー
        fieldnames = [
            'filename', 'path', 'score', 'is_good', 
            'dimensions_width', 'dimensions_height', 'size_bytes', 'format'
        ]
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for img_info in evaluated_images:
                # 評価結果からJSONを解析
                try:
                    if img_info.get('evaluation'):
                        evaluation = json.loads(img_info['evaluation'])
                    else:
                        evaluation = {}
                except:
                    evaluation = {}
                    
                # CSVに書き込む行データを作成
                row = {
                    'filename': img_info.get('filename', ''),
                    'path': str(img_info.get('path', '')),
                    'score': img_info.get('score', 0),
                    'is_good': 'Yes' if img_info.get('is_good', False) else 'No',
                    'dimensions_width': img_info.get('dimensions', (0, 0))[0],
                    'dimensions_height': img_info.get('dimensions', (0, 0))[1],
                    'size_bytes': img_info.get('size', 0),
                    'format': img_info.get('format', '')
                }
                
                writer.writerow(row)
                
        logger.info(f"CSV結果を保存しました: {csv_path}")
        
    def _copy_good_photos(self, good_images: List[Dict[str, Any]]) -> None:
        """
        良い写真を結果フォルダにコピー
        
        Args:
            good_images: 良い写真の情報リスト
        """
        if not good_images:
            logger.info("良い写真はありませんでした")
            return
            
        for img_info in good_images:
            src_path = img_info.get('path')
            if not src_path or not Path(src_path).exists():
                continue
                
            # 元のファイル名を保持しつつ、スコアを付加
            score = img_info.get('score', 0)
            filename = Path(src_path).name
            name, ext = os.path.splitext(filename)
            new_filename = f"{name}_score{score:.1f}{ext}"
            
            dst_path = self.good_photos_folder / new_filename
            
            try:
                shutil.copy2(src_path, dst_path)
                logger.info(f"写真をコピーしました: {src_path} -> {dst_path}")
            except Exception as e:
                logger.error(f"写真のコピーに失敗しました: {src_path} - {str(e)}")
                
        logger.info(f"{len(good_images)}枚の良い写真をコピーしました")
        
    def _generate_summary(self, evaluated_images: List[Dict[str, Any]], summary_path: Path) -> None:
        """
        サマリーレポートを生成
        
        Args:
            evaluated_images: 評価済みの画像情報リスト
            summary_path: 保存先のパス
        """
        if not evaluated_images:
            return
            
        good_images = [img for img in evaluated_images if img.get('is_good', False)]
        
        # スコア順にソート
        sorted_images = sorted(evaluated_images, key=lambda x: x.get('score', 0), reverse=True)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=== 写真評価サマリー ===\n\n")
            f.write(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"評価閾値: {QUALITY_THRESHOLD}\n\n")
            
            f.write(f"合計写真数: {len(evaluated_images)}\n")
            f.write(f"良い写真数: {len(good_images)} ({len(good_images)/len(evaluated_images)*100:.1f}%)\n\n")
            
            f.write("=== トップ10写真 ===\n\n")
            for i, img in enumerate(sorted_images[:10], 1):
                f.write(f"{i}. {img.get('filename', 'Unknown')} - スコア: {img.get('score', 0):.1f}\n")
                
                # 評価の詳細を追加
                if img.get('evaluation'):
                    try:
                        eval_dict = json.loads(img['evaluation'])
                        f.write(f"   説明: {eval_dict.get('description', 'N/A')}\n")
                        f.write(f"   強み: {eval_dict.get('strengths', 'N/A')}\n")
                        f.write(f"   改善点: {eval_dict.get('improvements', 'N/A')}\n")
                    except:
                        pass
                f.write("\n")
                
        logger.info(f"サマリーレポートを生成しました: {summary_path}")
