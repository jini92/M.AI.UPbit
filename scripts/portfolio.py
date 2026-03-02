#!/usr/bin/env python3
"""OpenClaw portfolio query script"""
import sys, os, json
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maiupbit.cli import cmd_portfolio
from argparse import Namespace

if __name__ == '__main__':
    fmt = sys.argv[1] if len(sys.argv) > 1 else 'json'
    args = Namespace(format=fmt)
    cmd_portfolio(args)