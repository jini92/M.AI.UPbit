#!/usr/bin/env python3
"""README.md shields.io 배지 자동 업데이트 스크립트.

<!-- BADGE_START --> ~ <!-- BADGE_END --> 섹션을 교체하거나,
섹션이 없으면 README.md 상단(# 제목 다음 줄)에 삽입합니다.

사용법:
    python scripts/update_readme_badge.py --signal cash --btc-price 100227000 --date 2026-03-09
    python scripts/update_readme_badge.py --signal buy  --btc-price 105000000 --date 2026-03-10 --push
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

BADGE_START = "<!-- BADGE_START -->"
BADGE_END = "<!-- BADGE_END -->"

SIGNAL_COLORS = {
    "cash": ("현금보유", "red"),
    "buy": ("매수신호", "brightgreen"),
    "sell": ("매도신호", "orange"),
}


def build_badge_block(signal: str, btc_price: int, date: str) -> str:
    """shields.io 배지 마크다운 블록 생성."""
    signal_label, signal_color = SIGNAL_COLORS.get(signal, ("알수없음", "lightgrey"))

    # 가격 포맷: 100,227,000 → 100.2M KRW
    price_m = btc_price / 1_000_000
    price_label = f"{price_m:.1f}M KRW"
    price_encoded = price_label.replace(" ", "%20")

    signal_encoded = signal_label.replace(" ", "%20")
    date_encoded = date.replace("-", "--")

    signal_badge = (
        f"[![전략시그널](https://img.shields.io/badge/전략시그널-{signal_encoded}-{signal_color}.svg)]"
        f"(https://pypi.org/project/maiupbit/)"
    )
    price_badge = (
        f"[![BTC현재가](https://img.shields.io/badge/BTC-{price_encoded}-yellow.svg)]"
        f"(https://upbit.com/exchange?code=CRIX.UPBIT.KRW-BTC)"
    )
    date_badge = (
        f"[![마지막업데이트](https://img.shields.io/badge/업데이트-{date_encoded}-blue.svg)]"
        f"(https://pypi.org/project/maiupbit/)"
    )

    return f"{BADGE_START}\n{signal_badge} {price_badge} {date_badge}\n{BADGE_END}"


def update_readme(readme_path: Path, badge_block: str) -> bool:
    """README.md에 배지 블록을 삽입하거나 교체한다. 변경 여부를 반환."""
    content = readme_path.read_text(encoding="utf-8")

    # 기존 BADGE 섹션이 있으면 교체
    pattern = re.compile(
        rf"{re.escape(BADGE_START)}.*?{re.escape(BADGE_END)}",
        flags=re.DOTALL,
    )
    if pattern.search(content):
        new_content = pattern.sub(badge_block, content)
    else:
        # 없으면 첫 번째 # 제목 바로 다음 줄에 삽입
        lines = content.splitlines(keepends=True)
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("#"):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, badge_block + "\n\n")
        new_content = "".join(lines)

    if new_content == content:
        return False

    readme_path.write_text(new_content, encoding="utf-8")
    return True


def git_commit_push(readme_path: Path, date: str, push: bool) -> None:
    """git add → commit → (선택) push."""
    rel = readme_path.name  # README.md

    subprocess.run(["git", "add", rel], check=True)
    commit_msg = f"chore: update README badges [{date}]"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)

    if push:
        subprocess.run(["git", "push"], check=True)
        print("Pushed to remote.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="README.md shields.io 배지 자동 업데이트"
    )
    parser.add_argument(
        "--signal",
        choices=["cash", "buy", "sell"],
        required=True,
        help="전략 시그널: cash(현금보유) | buy(매수) | sell(매도)",
    )
    parser.add_argument(
        "--btc-price",
        type=int,
        required=True,
        help="BTC 현재가 (KRW, 정수). 예: 100227000",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="기준 날짜 (YYYY-MM-DD). 예: 2026-03-09",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        default=False,
        help="git commit 후 origin으로 push",
    )
    parser.add_argument(
        "--readme",
        default="README.md",
        help="README 파일 경로 (기본값: README.md)",
    )
    args = parser.parse_args()

    readme_path = Path(args.readme)
    if not readme_path.exists():
        print(f"ERROR: {readme_path} 파일을 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    badge_block = build_badge_block(args.signal, args.btc_price, args.date)
    changed = update_readme(readme_path, badge_block)

    if not changed:
        print("배지 내용이 동일합니다. 변경 없음.")
        return

    print(f"README.md 배지 업데이트 완료 ({args.signal}, {args.btc_price:,} KRW, {args.date})")

    if args.push:
        git_commit_push(readme_path, args.date, push=True)
    else:
        subprocess.run(["git", "add", str(readme_path)], check=True)
        print("git add README.md 완료. 커밋하려면 --push 또는 수동으로 커밋하세요.")


if __name__ == "__main__":
    main()
