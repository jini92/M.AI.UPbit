"""Update README.md with latest weekly performance data"""
import json, sys, re
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
readme = Path("README.md").read_text(encoding="utf-8")

# 동적 배지 생성
date = report["date"]
signal = report["signal"]
top = report["top_coin"].replace("KRW-", "")
season = report["season"]["season"]
signal_color = "red" if signal == "CASH" else "brightgreen"
season_color = "brightgreen" if season == "bullish" else "orange"

# Weekly Performance 섹션 생성
perf_section = f"""
## 📊 Weekly Quant Signal (Auto-Updated)

| 항목 | 현황 |
|------|------|
| 업데이트 | {date} |
| 매매 시그널 | ![signal](https://img.shields.io/badge/Signal-{signal}-{signal_color}) |
| 시즌 | ![season](https://img.shields.io/badge/Season-{season}-{season_color}) |
| 모멘텀 1위 | {top} |

> 🤖 [maiupbit](https://pypi.org/project/maiupbit/) 엔진 자동 생성 · [뉴스레터 구독](#newsletter)

"""

# README에 섹션 삽입 (## Features 앞)
if "## 📊 Weekly Quant Signal" in readme:
    readme = re.sub(r"## 📊 Weekly Quant Signal.*?(?=## )", perf_section, readme, flags=re.DOTALL)
else:
    readme = readme.replace("## Features", perf_section + "## Features", 1)

Path("README.md").write_text(readme, encoding="utf-8")
print(f"✅ README updated: {date}, signal={signal}, top={top}")
