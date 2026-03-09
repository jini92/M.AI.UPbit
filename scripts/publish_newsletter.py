"""
Publish weekly quant newsletter to Substack via unofficial API.

Environment variables:
    SUBSTACK_COOKIE: substack.lli JWT cookie value
    SUBSTACK_URL: e.g. https://jinilee.substack.com
    DISCORD_WEBHOOK: Discord webhook URL for notifications
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


BLOG_PUBLISHED_DIR = Path(__file__).parent.parent / "blog" / "published"
SUBSTACK_API_PATH = "/api/v1/posts"


def _run_ci_report() -> dict:
    """Run ci_weekly_report.py and return parsed JSON output.

    Returns:
        Parsed quant data dictionary from ci_weekly_report.py stdout

    Raises:
        RuntimeError: If the script exits with a non-zero return code
    """
    script = Path(__file__).parent / "ci_weekly_report.py"
    print(f"[1/4] Running {script.name} ...")
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ci_weekly_report.py failed (exit {result.returncode}):\n{result.stderr}"
        )
    # Try to extract JSON from stdout (last JSON block)
    stdout = result.stdout.strip()
    # Find the last {...} block
    start = stdout.rfind("{")
    end = stdout.rfind("}") + 1
    if start == -1 or end == 0:
        print("[WARN] No JSON found in output, using empty data dict")
        return {}
    try:
        data = json.loads(stdout[start:end])
    except json.JSONDecodeError:
        print("[WARN] JSON parse error, using empty data dict")
        data = {}
    print(f"[1/4] Done. Keys: {list(data.keys())}")
    return data


def _get_issue_number() -> int:
    """Compute issue number from published blog posts count + 2.

    Returns:
        Issue number based on count of files in blog/published/ directory
    """
    if not BLOG_PUBLISHED_DIR.exists():
        BLOG_PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
        return 2
    count = sum(1 for f in BLOG_PUBLISHED_DIR.iterdir() if f.is_file())
    return count + 2


def _generate_html(data: dict) -> tuple[str, str, str]:
    """Generate HTML, title and subtitle from quant data.

    Args:
        data: Quant analysis result dictionary

    Returns:
        Tuple of (html_body, title, subtitle)
    """
    # Add project root to path for local imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.generate_newsletter_html import generate_html, get_title, get_subtitle  # noqa: PLC0415

    issue = _get_issue_number()
    print(f"[2/4] Generating HTML for issue #{issue} ...")
    html_body = generate_html(data, issue)
    title = get_title(data, issue)
    subtitle = get_subtitle(data)
    print(f"[2/4] Done. Title: {title}")
    return html_body, title, subtitle


def _publish_to_substack(html_body: str, title: str, subtitle: str) -> dict:
    """POST newsletter to Substack API.

    Args:
        html_body: Full HTML content of the newsletter
        title: Newsletter post title
        subtitle: Newsletter post subtitle

    Returns:
        Parsed JSON response from Substack API

    Raises:
        RuntimeError: If the API request fails
    """
    import urllib.request  # noqa: PLC0415

    substack_url = os.environ["SUBSTACK_URL"].rstrip("/")
    cookie_value = os.environ["SUBSTACK_COOKIE"]

    payload = json.dumps(
        {
            "type": "newsletter",
            "draft": False,
            "audience": "everyone",
            "title": title,
            "subtitle": subtitle,
            "body_html": html_body,
            "should_send_email": True,
        }
    ).encode("utf-8")

    url = f"{substack_url}{SUBSTACK_API_PATH}"
    print(f"[3/4] Publishing to {url} ...")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Cookie": f"substack.lli={cookie_value}",
            "Content-Type": "application/json",
            "User-Agent": "maiupbit-newsletter/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            print(f"[3/4] Published! Post ID: {result.get('id')}, URL: {result.get('canonical_url', 'N/A')}")
            return result
    except Exception as exc:
        # Re-raise with HTTP body if available
        raise RuntimeError(f"Substack API error: {exc}") from exc


def _notify_discord(success: bool, title: str, post_url: str = "", error: str = "") -> None:
    """Send result notification to Discord webhook.

    Args:
        success: Whether the publish operation succeeded
        title: Newsletter title for the notification message
        post_url: Published post URL (used on success)
        error: Error message string (used on failure)
    """
    import urllib.request  # noqa: PLC0415

    webhook_url = os.environ.get("DISCORD_WEBHOOK", "")
    if not webhook_url:
        print("[4/4] DISCORD_WEBHOOK not set, skipping notification.")
        return

    if success:
        payload = {
            "embeds": [
                {
                    "title": "Newsletter Published",
                    "description": f"**{title}**",
                    "color": 0x27AE60,
                    "fields": [
                        {"name": "Substack URL", "value": post_url or "N/A", "inline": False}
                    ],
                    "footer": {"text": "maiupbit newsletter auto-publish"},
                }
            ]
        }
    else:
        payload = {
            "embeds": [
                {
                    "title": "Newsletter Publish Failed",
                    "description": f"**{title}**\n```{error[:500]}```",
                    "color": 0xE74C3C,
                    "footer": {"text": "maiupbit newsletter auto-publish"},
                }
            ]
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10):
            print("[4/4] Discord notification sent.")
    except Exception as exc:
        print(f"[4/4] Discord notification failed: {exc}")


def main() -> None:
    """Main entry point for newsletter publishing pipeline."""
    # Validate required env vars
    missing = [v for v in ("SUBSTACK_COOKIE", "SUBSTACK_URL") if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing required environment variables: {missing}")
        sys.exit(1)

    title = "M.AI.UPbit Weekly Report"
    try:
        # Step 1: Generate quant data
        data = _run_ci_report()

        # Step 2: Generate HTML
        html_body, title, subtitle = _generate_html(data)

        # Step 3: Publish to Substack
        result = _publish_to_substack(html_body, title, subtitle)

        post_url = result.get("canonical_url", "")
        # Step 4: Notify Discord (success)
        _notify_discord(success=True, title=title, post_url=post_url)

        print("\n=== Newsletter published successfully ===")
        print(f"Title   : {title}")
        print(f"Post URL: {post_url}")

    except Exception as exc:
        error_msg = str(exc)
        print(f"\nERROR: {error_msg}")
        _notify_discord(success=False, title=title, error=error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
