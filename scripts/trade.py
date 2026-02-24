#!/usr/bin/env python3
"""OpenClaw용 매매 실행 스크립트 — confirm 플래그 필수"""
import sys, os, json
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maiupbit.cli import cmd_trade
from argparse import Namespace

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: trade.py <buy|sell> <symbol> <amount> [--confirm]"}))
        sys.exit(1)

    action = sys.argv[1]
    symbol = sys.argv[2]
    amount = float(sys.argv[3])
    confirm = '--confirm' in sys.argv

    args = Namespace(action=action, symbol=symbol, amount=amount, confirm=confirm, format='json')
    cmd_trade(args)
