"""把今日日报摘要推送到 Telegram。

环境变量:
  TELEGRAM_BOT_TOKEN  必填,@BotFather 给的 token
  TELEGRAM_CHAT_ID    必填,你的 chat_id(私聊或群组)
  GITHUB_REPOSITORY   选填,GitHub Actions 自动注入,用于生成"查看完整日报"链接

只发送日报标题 + Top 5 涨幅榜 + Top 5 跌幅榜,
正文超过 4000 字符会自动截断(Telegram 上限 4096)。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


def send_telegram(token: str, chat_id: str, text: str) -> dict:
    """调用 Telegram Bot API 发送消息(HTML 格式)。"""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def html_escape(s: str) -> str:
    """Telegram HTML 模式需要转义这三个字符。"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(report_path: Path, repo_url: str) -> str:
    """从 Markdown 日报中抽取标题 + Top 涨跌幅榜,转成 Telegram HTML。"""
    text = report_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    out: list[str] = []
    in_top_section = False

    for ln in lines:
        # 一级标题(日报主标题)
        if ln.startswith("# "):
            out.append(f"📊 <b>{html_escape(ln[2:].strip())}</b>")
            continue

        # 二级标题:只关心 Top 5 涨跌幅
        if ln.startswith("## "):
            heading = ln[3:].strip()
            if heading.startswith("今日 Top"):
                in_top_section = True
                emoji = "📈" if "涨" in heading else "📉"
                out.append(f"\n{emoji} <b>{html_escape(heading)}</b>")
                continue
            else:
                in_top_section = False
                continue

        if not in_top_section:
            continue

        # 表格数据行(过滤掉表头和分隔行)
        if ln.startswith("|") and not ln.startswith("|---") and "Ticker" not in ln:
            cells = [c.strip().replace("**", "") for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 4:
                ticker, name, pct, price = cells[0], cells[1], cells[2], cells[3]
                # 跳过空行(没有有效 ticker)
                if not ticker:
                    continue
                line = (
                    f"  <code>{html_escape(ticker)}</code>  "
                    f"<b>{html_escape(pct)}</b>  "
                    f"{html_escape(price)}  — {html_escape(name[:24])}"
                )
                out.append(line)

    out.append(f"\n🔗 <a href=\"{repo_url}\">查看完整日报</a>")
    return "\n".join(out)


def find_latest_report() -> Path | None:
    """优先取今日报告,否则取目录里最新的一份。"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_path = Path("reports") / f"{today}.md"
    if today_path.exists():
        return today_path
    candidates = sorted(Path("reports").glob("*.md"))
    return candidates[-1] if candidates else None


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未配置,跳过推送。")
        return 0  # 不算失败,优雅退出

    report = find_latest_report()
    if report is None:
        print("⚠ 找不到任何日报文件,跳过推送。")
        return 0

    repo = os.environ.get("GITHUB_REPOSITORY", "ProWD888/text")
    repo_url = f"https://github.com/{repo}/blob/main/{report.as_posix()}"

    msg = build_message(report, repo_url)
    # Telegram 单条消息上限 4096 字符
    if len(msg) > 4000:
        msg = msg[:3950] + "\n…(已截断,完整内容点链接)"

    try:
        result = send_telegram(token, chat_id, msg)
    except Exception as e:  # noqa: BLE001
        print(f"✗ Telegram 推送失败: {type(e).__name__}: {e}")
        return 1

    if result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"✓ Telegram 已推送,message_id={msg_id}")
        return 0
    print(f"✗ Telegram 返回错误: {result}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
