#!/usr/bin/env python3
"""
写真評価ツール（Whale）のエントリーポイント
"""

import sys
import os
from pathlib import Path

def main():
    # whale/src/main.pyへのパスを取得
    current_dir = Path(__file__).parent
    src_main_path = current_dir / "whale" / "src" / "main.py"
    
    # コマンドライン引数を渡して実行
    sys.path.insert(0, str(current_dir))
    from whale.src.main import main as whale_main
    
    # メイン関数を実行
    whale_main()

if __name__ == "__main__":
    main()
