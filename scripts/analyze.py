#!/usr/bin/env python3
"""OpenClaw analysis execution script"""
import sys
import json
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maiupbit.cli import cmd_analyze
from argparse import Namespace

if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'KRW-BTC'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    args = Namespace(symbol=symbol, days=days, format='json')
    cmd_analyze(args)