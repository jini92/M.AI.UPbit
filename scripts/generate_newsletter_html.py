"""Generate HTML newsletter from quant data dictionary."""
from __future__ import annotations

import html
from datetime import datetime, timezone, timedelta
from typing import Any


KST = timezone(timedelta(hours=9))


def _safe(val: Any, fmt: str = "") -> str:
    """Format value safely."""
    if val is None or val == "N/A":
        return "N/A"
    try:
        if fmt:
            return format(float(val), fmt)
        return str(val)
    except (TypeError, ValueError):
        return str(val)


def generate_html(data: dict[str, Any], issue_number: int) -> str:
    """
    Generate English newsletter HTML from quant data.

    Args:
        data: Quant analysis result dictionary from ci_weekly_report.py
        issue_number: Newsletter issue number

    Returns:
        Full HTML string for Substack newsletter body
    """
    now = datetime.now(KST)
    date_str = now.strftime("%B %d, %Y")
    week_str = now.strftime("Week %W, %Y")

    # ── Market Season Section ──────────────────────────────────────────────
    season = data.get("season", {})
    season_name = html.escape(str(season.get("season_name", "N/A")))
    season_score = _safe(season.get("score"), ".1f")
    season_signal = html.escape(str(season.get("signal", "N/A")))
    halving_info = html.escape(str(season.get("halving_info", "")))

    # ── Dual Momentum TOP5 ────────────────────────────────────────────────
    momentum_coins = data.get("momentum_top5", [])
    momentum_rows = ""
    for i, coin in enumerate(momentum_coins[:5], 1):
        ticker = html.escape(str(coin.get("ticker", "")))
        score = _safe(coin.get("momentum_score"), ".3f")
        signal = html.escape(str(coin.get("signal", "")))
        signal_color = "#27ae60" if "BUY" in signal.upper() else "#e74c3c" if "SELL" in signal.upper() else "#7f8c8d"
        momentum_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;font-weight:bold;">{i}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;">{ticker}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;text-align:right;">{score}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;color:{signal_color};font-weight:bold;">{signal}</td>
        </tr>"""

    if not momentum_rows:
        momentum_rows = '<tr><td colspan="4" style="padding:16px;text-align:center;color:#95a5a6;">No data available</td></tr>'

    # ── Multi-Factor Ranking TOP5 ─────────────────────────────────────────
    factor_coins = data.get("factor_top5", [])
    factor_rows = ""
    for i, coin in enumerate(factor_coins[:5], 1):
        ticker = html.escape(str(coin.get("ticker", "")))
        rank = _safe(coin.get("rank"))
        score = _safe(coin.get("factor_score"), ".3f")
        factor_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;font-weight:bold;">{i}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;">{ticker}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;text-align:right;">{rank}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;text-align:right;">{score}</td>
        </tr>"""

    if not factor_rows:
        factor_rows = '<tr><td colspan="4" style="padding:16px;text-align:center;color:#95a5a6;">No data available</td></tr>'

    # ── GTAA Allocation ───────────────────────────────────────────────────
    allocation = data.get("gtaa_allocation", {})
    alloc_rows = ""
    for asset, weight in allocation.items():
        asset_esc = html.escape(str(asset))
        weight_pct = _safe(float(weight) * 100 if weight is not None else None, ".1f")
        bar_width = int(float(weight) * 100) if weight is not None else 0
        alloc_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;">{asset_esc}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;text-align:right;">{weight_pct}%</td>
          <td style="padding:8px 12px;border-bottom:1px solid #ecf0f1;width:200px;">
            <div style="background:#ecf0f1;border-radius:4px;height:16px;">
              <div style="background:#3498db;border-radius:4px;height:16px;width:{bar_width}%;"></div>
            </div>
          </td>
        </tr>"""

    if not alloc_rows:
        alloc_rows = '<tr><td colspan="3" style="padding:16px;text-align:center;color:#95a5a6;">No allocation data</td></tr>'

    # ── Weekly Signal Summary ─────────────────────────────────────────────
    signals = data.get("weekly_signals", {})
    breakout_signal = html.escape(str(signals.get("volatility_breakout", "N/A")))
    momentum_signal = html.escape(str(signals.get("dual_momentum", "N/A")))
    factor_signal = html.escape(str(signals.get("multi_factor", "N/A")))
    overall = html.escape(str(signals.get("overall", "NEUTRAL")))
    overall_color = "#27ae60" if "BUY" in overall.upper() else "#e74c3c" if "SELL" in overall.upper() else "#f39c12"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>M.AI.UPbit Weekly Quant Report #{issue_number}</title>
</head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:'Segoe UI',Arial,sans-serif;color:#2c3e50;">

<div style="max-width:680px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);padding:40px 32px;text-align:center;">
    <div style="font-size:12px;color:#e94560;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">Weekly Quant Intelligence</div>
    <h1 style="margin:0;font-size:28px;color:#ffffff;font-weight:700;">M.AI.UPbit Report</h1>
    <div style="margin-top:8px;font-size:14px;color:#a8b2d8;">Issue #{issue_number} &nbsp;&middot;&nbsp; {date_str} &nbsp;&middot;&nbsp; {week_str}</div>
    <div style="margin-top:4px;font-size:12px;color:#6a7a9b;">Powered by maiupbit &mdash; Apache 2.0 OSS</div>
  </div>

  <!-- Intro -->
  <div style="padding:24px 32px;background:#f0f4ff;border-bottom:2px solid #e8eeff;">
    <p style="margin:0;font-size:15px;line-height:1.7;color:#34495e;">
      Your weekly automated quant analysis for the Korean crypto market (UPbit).
      Data is generated by <strong>maiupbit</strong> &mdash; an open-source AI digital asset analysis engine &mdash;
      using Kang Hwan-kuk's quantitative strategy framework.
    </p>
  </div>

  <!-- Section 1: Market Season -->
  <div style="padding:28px 32px;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1a1a2e;border-left:4px solid #e94560;padding-left:12px;">
      &#128197; Market Season Analysis
    </h2>
    <div style="background:#fafbff;border:1px solid #e8eeff;border-radius:8px;padding:20px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;width:40%;">Current Season</td>
          <td style="padding:8px 0;font-weight:bold;font-size:15px;">{season_name}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;">Season Score</td>
          <td style="padding:8px 0;font-weight:bold;">{season_score}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;">Signal</td>
          <td style="padding:8px 0;font-weight:bold;color:#e94560;">{season_signal}</td>
        </tr>
        {"<tr><td style='padding:8px 0;color:#7f8c8d;font-size:13px;'>Halving Info</td><td style='padding:8px 0;font-size:13px;'>" + halving_info + "</td></tr>" if halving_info else ""}
      </table>
    </div>
  </div>

  <!-- Section 2: Dual Momentum TOP5 -->
  <div style="padding:0 32px 28px;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1a1a2e;border-left:4px solid #3498db;padding-left:12px;">
      &#128640; Dual Momentum TOP 5
    </h2>
    <div style="border-radius:8px;overflow:hidden;border:1px solid #e8eeff;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#1a1a2e;color:#ffffff;">
            <th style="padding:10px 12px;text-align:left;font-size:13px;">#</th>
            <th style="padding:10px 12px;text-align:left;font-size:13px;">Ticker</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;">Momentum Score</th>
            <th style="padding:10px 12px;text-align:left;font-size:13px;">Signal</th>
          </tr>
        </thead>
        <tbody>
          {momentum_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Section 3: Multi-Factor Ranking TOP5 -->
  <div style="padding:0 32px 28px;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1a1a2e;border-left:4px solid #9b59b6;padding-left:12px;">
      &#128202; Multi-Factor Ranking TOP 5
    </h2>
    <div style="border-radius:8px;overflow:hidden;border:1px solid #e8eeff;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#1a1a2e;color:#ffffff;">
            <th style="padding:10px 12px;text-align:left;font-size:13px;">#</th>
            <th style="padding:10px 12px;text-align:left;font-size:13px;">Ticker</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;">Rank</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;">Factor Score</th>
          </tr>
        </thead>
        <tbody>
          {factor_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Section 4: GTAA Allocation -->
  <div style="padding:0 32px 28px;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1a1a2e;border-left:4px solid #27ae60;padding-left:12px;">
      &#127757; GTAA Asset Allocation
    </h2>
    <div style="border-radius:8px;overflow:hidden;border:1px solid #e8eeff;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#1a1a2e;color:#ffffff;">
            <th style="padding:10px 12px;text-align:left;font-size:13px;">Asset</th>
            <th style="padding:10px 12px;text-align:right;font-size:13px;">Weight</th>
            <th style="padding:10px 12px;font-size:13px;width:200px;">Allocation</th>
          </tr>
        </thead>
        <tbody>
          {alloc_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Section 5: Weekly Signal Summary -->
  <div style="padding:0 32px 28px;">
    <h2 style="margin:0 0 16px;font-size:18px;color:#1a1a2e;border-left:4px solid #f39c12;padding-left:12px;">
      &#9889; Weekly Signal Summary
    </h2>
    <div style="background:#fafbff;border:1px solid #e8eeff;border-radius:8px;padding:20px;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;width:50%;">Volatility Breakout</td>
          <td style="padding:8px 0;font-weight:bold;">{breakout_signal}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;">Dual Momentum</td>
          <td style="padding:8px 0;font-weight:bold;">{momentum_signal}</td>
        </tr>
        <tr>
          <td style="padding:8px 0;color:#7f8c8d;font-size:13px;">Multi-Factor</td>
          <td style="padding:8px 0;font-weight:bold;">{factor_signal}</td>
        </tr>
        <tr style="border-top:2px solid #e8eeff;">
          <td style="padding:12px 0 8px;color:#2c3e50;font-size:14px;font-weight:bold;">Overall Signal</td>
          <td style="padding:12px 0 8px;font-size:16px;font-weight:bold;color:{overall_color};">{overall}</td>
        </tr>
      </table>
    </div>
  </div>

  <!-- Disclaimer -->
  <div style="padding:0 32px 20px;">
    <div style="background:#fff9f0;border:1px solid #fde8c8;border-radius:8px;padding:16px;">
      <p style="margin:0;font-size:12px;color:#8d6e63;line-height:1.6;">
        &#9888;&#65039; <strong>Disclaimer:</strong> This newsletter is generated automatically by an open-source
        quantitative model. It is for informational purposes only and does not constitute financial advice.
        Always do your own research before making investment decisions.
        Past performance does not guarantee future results.
      </p>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#1a1a2e;padding:24px 32px;text-align:center;">
    <p style="margin:0 0 8px;font-size:13px;color:#a8b2d8;">
      Powered by <strong style="color:#e94560;">maiupbit</strong> (Apache 2.0)
    </p>
    <p style="margin:0;font-size:12px;">
      <a href="https://github.com/jini92/M.AI.UPbit" style="color:#6a7a9b;text-decoration:none;">
        github.com/jini92/M.AI.UPbit
      </a>
    </p>
    <p style="margin:8px 0 0;font-size:11px;color:#4a5568;">
      Generated {now.strftime("%Y-%m-%d %H:%M KST")} &nbsp;&middot;&nbsp; Issue #{issue_number}
    </p>
  </div>

</div>
</body>
</html>"""

    return html_content


def get_title(data: dict[str, Any], issue_number: int) -> str:
    """Generate newsletter title.

    Args:
        data: Quant analysis result dictionary
        issue_number: Newsletter issue number

    Returns:
        Formatted newsletter title string
    """
    now = datetime.now(KST)
    week_str = now.strftime("Week %W")
    season = data.get("season", {}).get("season_name", "")
    overall = data.get("weekly_signals", {}).get("overall", "NEUTRAL")
    signal_emoji = "🟢" if "BUY" in str(overall).upper() else "🔴" if "SELL" in str(overall).upper() else "🟡"
    season_part = f" | {season}" if season and season != "N/A" else ""
    return f"M.AI.UPbit #{issue_number} — {week_str}{season_part} {signal_emoji} {overall}"


def get_subtitle(data: dict[str, Any]) -> str:
    """Generate newsletter subtitle.

    Args:
        data: Quant analysis result dictionary

    Returns:
        Formatted newsletter subtitle string
    """
    now = datetime.now(KST)
    momentum_top = data.get("momentum_top5", [{}])
    top_coin = momentum_top[0].get("ticker", "").replace("KRW-", "") if momentum_top else ""
    top_part = f" | Top momentum: {top_coin}" if top_coin else ""
    return f"Weekly quant signals for Korean crypto market{top_part} — {now.strftime('%b %d, %Y')}"
