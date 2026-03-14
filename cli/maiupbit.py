#!/usr/bin/env python3
"""maiupbit -- M.AI.UPbit CLI for MAIJini orchestration.

Click-based wrapper for all M.AI.UPbit scripts.
All commands output JSON by default for agent consumption.

Install:
    pip install -e "C:\\TEST\\M.AI.UPbit"

Usage:
    maiupbit status
    maiupbit momentum --top 5 --json
    maiupbit monitor --json
    maiupbit season --json
    maiupbit report --json
    maiupbit allocate --json
    maiupbit breakout --symbol KRW-ETH
    maiupbit factor --top 3 --json
    maiupbit backtest momentum --days 365
    maiupbit analyze --symbol KRW-BTC
"""
import json
import os
import sys
import subprocess
from pathlib import Path

import click
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_DIR / "scripts"

# Auto-load .env from project root
load_dotenv(PROJECT_DIR / ".env")

# Ensure project is on sys.path for direct imports
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def _run_script(script_name: str, args: list) -> subprocess.CompletedProcess:
    """Run a script from scripts/ directory with correct environment."""
    env = {
        **os.environ,
        "PYTHONPATH": str(PROJECT_DIR),
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script_name)] + args,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_DIR),
        env=env,
    )


def _forward_output(result: subprocess.CompletedProcess, json_mode: bool) -> None:
    """Forward subprocess result to stdout, handling errors."""
    if result.returncode != 0:
        err = result.stderr.strip() or "Script execution failed"
        if json_mode:
            click.echo(json.dumps({"error": err}, ensure_ascii=False), err=True)
        else:
            click.secho(f"[ERROR] {err}", fg="red", err=True)
        sys.exit(result.returncode)
    click.echo(result.stdout, nl=False)


@click.group(invoke_without_command=True)
@click.version_option("1.0.0", prog_name="maiupbit")
@click.pass_context
def cli(ctx):
    """M.AI.UPbit -- AI-powered crypto quant analysis CLI.

    \b
    Quick start:
      maiupbit status                    # BTC quick snapshot
      maiupbit momentum --top 5 --json   # Dual momentum ranking
      maiupbit monitor --json            # Market monitoring
      maiupbit season --json             # Season cycle analysis
      maiupbit report --json             # Daily analysis report
      maiupbit allocate --json           # GTAA asset allocation
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# --------------------------------------------------------------------------- #
#  status                                                                       #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbol", default="KRW-BTC", help="Market symbol (default: KRW-BTC)")
@click.option("--json/--no-json", "json_mode", default=True, help="JSON output (default: on)")
def status(symbol: str, json_mode: bool):
    """Quick market snapshot: current price, 24h change, RSI."""
    try:
        from maiupbit.exchange.upbit import UPbitExchange
        from maiupbit.indicators import momentum as mom_ind

        exchange = UPbitExchange()
        daily = exchange.get_ohlcv(symbol, "day", count=2)
        hourly = exchange.get_ohlcv(symbol, "minute60", count=24)

        if daily is None or len(daily) < 2:
            msg = f"Failed to fetch {symbol} data"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.secho(f"[ERROR] {msg}", fg="red", err=True)
            sys.exit(1)

        curr = float(daily["close"].iloc[-1])
        prev = float(daily["close"].iloc[-2])
        change_pct = (curr - prev) / prev * 100

        rsi_val = None
        if hourly is not None and len(hourly) >= 14:
            rsi_val = float(mom_ind.rsi(hourly["close"], 14).iloc[-1])

        result = {
            "symbol": symbol,
            "price": curr,
            "change_24h_pct": round(change_pct, 2),
            "rsi_14": round(rsi_val, 2) if rsi_val is not None else None,
            "signal": (
                "overbought" if rsi_val and rsi_val > 70
                else "oversold" if rsi_val and rsi_val < 30
                else "neutral"
            ),
        }
        if json_mode:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            click.echo(f"Symbol : {result['symbol']}")
            click.echo(f"Price  : {result['price']:,.0f} KRW")
            click.echo(f"24h    : {result['change_24h_pct']:+.2f}%")
            click.echo(f"RSI-14 : {result['rsi_14']}")
            click.echo(f"Signal : {result['signal']}")
    except Exception as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.secho(f"[ERROR] {exc}", fg="red", err=True)
        sys.exit(1)


# --------------------------------------------------------------------------- #
#  momentum                                                                     #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--top", default=5, type=int, help="Top N coins (default: 5)")
@click.option("--symbols", default=None, help="Comma-separated symbol list")
@click.option("--days", default=400, type=int, help="History days (default: 400)")
@click.option("--json/--no-json", "json_mode", default=True)
def momentum(top: int, symbols: str, days: int, json_mode: bool):
    """Dual momentum strategy ranking.

    \b
    Example:
      maiupbit momentum --top 5 --json
      maiupbit momentum --symbols KRW-BTC,KRW-ETH,KRW-SOL --top 3
    """
    args = ["momentum", "--top", str(top), "--days", str(days)]
    if symbols:
        args += ["--symbols", symbols]
    _forward_output(_run_script("quant.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  breakout                                                                     #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbol", default="KRW-BTC", help="Symbol (default: KRW-BTC)")
@click.option("--k", default=0.5, type=float, help="K value (default: 0.5)")
@click.option("--days", default=60, type=int, help="History days (default: 60)")
@click.option("--json/--no-json", "json_mode", default=True)
def breakout(symbol: str, k: float, days: int, json_mode: bool):
    """Volatility breakout signal detection.

    \b
    Example:
      maiupbit breakout --symbol KRW-ETH --json
    """
    _forward_output(
        _run_script("quant.py", ["breakout", symbol, "--k", str(k), "--days", str(days)]),
        json_mode,
    )


# --------------------------------------------------------------------------- #
#  factor                                                                       #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--top", default=5, type=int, help="Top N coins (default: 5)")
@click.option("--symbols", default=None, help="Comma-separated symbol list")
@click.option("--days", default=200, type=int, help="History days (default: 200)")
@click.option("--json/--no-json", "json_mode", default=True)
def factor(top: int, symbols: str, days: int, json_mode: bool):
    """Multi-factor ranking strategy.

    \b
    Example:
      maiupbit factor --top 3 --json
    """
    args = ["factor", "--top", str(top), "--days", str(days)]
    if symbols:
        args += ["--symbols", symbols]
    _forward_output(_run_script("quant.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  allocate                                                                     #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbols", default=None, help="Comma-separated symbols for GTAA")
@click.option("--days", default=400, type=int, help="History days (default: 400)")
@click.option("--json/--no-json", "json_mode", default=True)
def allocate(symbols: str, days: int, json_mode: bool):
    """GTAA (Global Tactical Asset Allocation) strategy.

    \b
    Example:
      maiupbit allocate --json
    """
    args = ["allocate", "--days", str(days)]
    if symbols:
        args += ["--symbols", symbols]
    _forward_output(_run_script("quant.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  season                                                                       #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--json/--no-json", "json_mode", default=True)
def season(json_mode: bool):
    """Market season/cycle analysis (halving cycle filter).

    \b
    Example:
      maiupbit season --json
    """
    _forward_output(_run_script("quant.py", ["season"]), json_mode)


# --------------------------------------------------------------------------- #
#  backtest                                                                     #
# --------------------------------------------------------------------------- #

@cli.command()
@click.argument("strategy", type=click.Choice(["momentum", "breakout", "factor", "allocate"]))
@click.option("--symbols", default=None, help="Comma-separated symbol list")
@click.option("--days", default=365, type=int, help="Backtest period days (default: 365)")
@click.option("--json/--no-json", "json_mode", default=True)
def backtest(strategy: str, symbols: str, days: int, json_mode: bool):
    """Strategy backtesting.

    \b
    Example:
      maiupbit backtest momentum --days 365 --json
    """
    args = ["backtest", strategy, "--days", str(days)]
    if symbols:
        args += ["--symbols", symbols]
    _forward_output(_run_script("quant.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  monitor                                                                      #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbols", default=None, help="Comma-separated symbols to monitor")
@click.option("--json/--no-json", "json_mode", default=True)
def monitor(symbols: str, json_mode: bool):
    """Multi-coin monitoring -- check 24h changes and RSI alerts.

    \b
    Example:
      maiupbit monitor --json
      maiupbit monitor --symbols KRW-BTC,KRW-ETH,KRW-SOL --json
    """
    args = symbols.split(",") if symbols else []
    _forward_output(_run_script("monitor.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  report                                                                       #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbols", default=None, help="Comma-separated symbols (default: BTC,ETH,XRP)")
@click.option("--json/--no-json", "json_mode", default=True)
def report(symbols: str, json_mode: bool):
    """Generate daily analysis report.

    \b
    Example:
      maiupbit report --json
    """
    args = symbols.split(",") if symbols else []
    _forward_output(_run_script("daily_report.py", args), json_mode)


# --------------------------------------------------------------------------- #
#  analyze                                                                      #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--symbol", "-s", default="KRW-BTC", help="Coin symbol (default: KRW-BTC)")
@click.option("--days", "-d", default=30, type=int, help="Analysis period days (default: 30)")
@click.option("--json/--no-json", "json_mode", default=True)
def analyze(symbol: str, days: int, json_mode: bool):
    """Technical + LLM analysis for a coin.

    \b
    Example:
      maiupbit analyze --symbol KRW-ETH --json
    """
    _forward_output(_run_script("analyze.py", [symbol, str(days)]), json_mode)


# --------------------------------------------------------------------------- #
#  portfolio                                                                    #
# --------------------------------------------------------------------------- #

@cli.command()
@click.option("--json/--no-json", "json_mode", default=True)
def portfolio(json_mode: bool):
    """View current portfolio holdings.

    Requires UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY in .env.

    \b
    Example:
      maiupbit portfolio --json
    """
    try:
        from maiupbit.exchange.upbit import UPbitExchange

        access_key = os.getenv("UPBIT_ACCESS_KEY")
        secret_key = os.getenv("UPBIT_SECRET_KEY")
        if not access_key or not secret_key:
            msg = "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY required in .env"
            if json_mode:
                click.echo(json.dumps({"error": msg}), err=True)
            else:
                click.secho(f"[ERROR] {msg}", fg="red", err=True)
            sys.exit(1)

        exchange = UPbitExchange(access_key=access_key, secret_key=secret_key)
        result = exchange.get_portfolio()
        if json_mode:
            click.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            for asset in result.get("assets", []):
                click.echo(f"  {asset['symbol']}: {asset['quantity']:.8f}")
            click.echo(f"  Total: {result.get('total_value', 0):,.0f} KRW")
    except Exception as exc:
        if json_mode:
            click.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            click.secho(f"[ERROR] {exc}", fg="red", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
