#!/usr/bin/env python3
"""
写真評価ツール（Whale）のエントリーポイント
"""

import sys
import os
from pathlib import Path

def main():
    # src/main.pyへのパスを取得
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    
    # メイン関数を実行
    from src.main import main as whale_main
    whale_main()

if __name__ == "__main__":
    main()
