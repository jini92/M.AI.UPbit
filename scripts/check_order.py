#!/usr/bin/env python3
"""주문 체결 확인 스크립트."""
import json
import os
import sys

import requests
import jwt
import uuid
import hashlib
from urllib.parse import urlencode, unquote
from dotenv import load_dotenv

load_dotenv()

ak = os.getenv("UPBIT_ACCESS_KEY")
sk = os.getenv("UPBIT_SECRET_KEY")

# 1) 잔고 확인
import pyupbit
upbit = pyupbit.Upbit(ak, sk)
balances = upbit.get_balances()
print("=== 잔고 ===")
for b in balances:
    bal = float(b.get("balance", 0))
    if bal > 0:
        cur = b["currency"]
        avg = b.get("avg_buy_price", "?")
        print(f"  {cur}: {bal:,.2f} (avg: {avg})")

# 2) 주문 확인
order_uuid = sys.argv[1] if len(sys.argv) > 1 else "c94a9433-aa57-42de-9162-1c24fc26d2aa"
query = {"uuid": order_uuid}
query_string = unquote(urlencode(query, doseq=True)).encode("utf-8")
m = hashlib.sha512()
m.update(query_string)
query_hash = m.hexdigest()

payload = {
    "access_key": ak,
    "nonce": str(uuid.uuid4()),
    "query_hash": query_hash,
    "query_hash_alg": "SHA512",
}
token = jwt.encode(payload, sk)
headers = {"Authorization": f"Bearer {token}"}
res = requests.get("https://api.upbit.com/v1/order", params=query, headers=headers)
print(f"\n=== 주문 ({order_uuid[:12]}...) ===")
print(f"Status: {res.status_code}")
if res.status_code == 200:
    order = res.json()
    print(json.dumps(order, indent=2, default=str, ensure_ascii=False))
else:
    print(res.text)
