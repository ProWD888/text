"""把今日日报摘要推送到 Telegram(等宽字体表格版)。

环境变量:
  TELEGRAM_BOT_TOKEN  必填,@BotFather 给的 token
  TELEGRAM_CHAT_ID    必填,你的 chat_id(私聊或群组)
  GITHUB_REPOSITORY   选填,GitHub Actions 自动注入,用于生成"查看完整日报"链接

只发送日报标题 + Top 5 涨幅榜 + Top 5 跌幅榜,
正文超过 4000 字符会自动截断(Telegram 上限 4096)。

排版策略:
  使用 <pre> 标签包裹表格,Telegram 客户端会用等宽字体渲染,
  ticker / 涨跌幅 / 价格三列严格对齐,扫一眼就能读懂。
  公司名只取破折号前的主名(如 "Qualcomm — RB6/RB7 机器人平台" → "Qualcomm")。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


# --------------------------------------------------------------------------- #
# Telegram API
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Markdown report parsing
# --------------------------------------------------------------------------- #
def short_name(desc: str, max_len: int = 18) -> str:
    """把 'Qualcomm — RB6/RB7 机器人平台' 简化为 'Qualcomm'。"""
    for sep in ["—", "–", " - "]:
        if sep in desc:
            desc = desc.split(sep)[0]
            break
    return desc.strip()[:max_len]


def parse_report(report_path: Path) -> dict:
    """从 Markdown 日报中提取:title, date, gainers, losers。"""
    text = report_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    title = ""
    date_str = ""
    gainers: list[dict] = []
    losers: list[dict] = []
    current: list[dict] | None = None

    for ln in lines:
        if ln.startswith("# "):
            full_title = ln[2:].strip()
            # 标题里通常带日期: "人形机器人产业链日报 — 2026-05-23 10:57"
            m = re.match(r"^(.*?)\s*[—–-]\s*(\d{4}-\d{2}-\d{2}.*)$", full_title)
            if m:
                title = m.group(1).strip()
                date_str = m.group(2).strip()
            else:
                title = full_title
        elif ln.startswith("## 今日 Top") and "涨" in ln:
            current = gainers
        elif ln.startswith("## 今日 Top") and "跌" in ln:
            current = losers
        elif ln.startswith("## "):
            current = None
        elif (
            current is not None
            and ln.startswith("|")
            and not ln.startswith("|---")
            and "Ticker" not in ln
        ):
            cells = [
                c.strip().replace("**", "")
                for c in ln.strip().strip("|").split("|")
            ]
            if len(cells) >= 4 and cells[0]:
                current.append(
                    {
                        "ticker": cells[0],
                        "name": short_name(cells[1]),
                        "pct": cells[2],
                        "price": cells[3],
                    }
                )

    return {
        "title": title,
        "date": date_str,
        "gainers": gainers,
        "losers": losers,
    }


# --------------------------------------------------------------------------- #
# Message rendering
# --------------------------------------------------------------------------- #
def display_width(s: str) -> int:
    """计算字符串在等宽字体下的显示宽度。

    CJK/全角字符按 2 列计算,其它(ASCII)按 1 列计算。
    Telegram 等宽字体下,中文 1 个字 ≈ 英文 2 个字符的宽度。
    """
    return sum(2 if ord(c) > 127 else 1 for c in s)


def pad_right(s: str, target: int) -> str:
    """左对齐:在右侧补空格到目标显示宽度。"""
    return s + " " * max(0, target - display_width(s))


def pad_left(s: str, target: int) -> str:
    """右对齐:在左侧补空格到目标显示宽度。"""
    return " " * max(0, target - display_width(s)) + s


def format_table(rows: list[dict]) -> str:
    """把行数据格式化为等宽字体下对齐的表格文本(带中文表头)。

    输出形如:
        代码    涨跌幅      现价  公司
        QCOM   +11.60%  $238.16  Qualcomm
        F       +9.22%   $14.93  Ford
    """
    if not rows:
        return ""

    headers = {
        "ticker": "代码",
        "pct": "涨跌幅",
        "price": "现价",
        "name": "公司",
    }

    # 列宽 = max(表头宽度, 该列所有数据宽度),保证表头和数据都不被截断
    w_ticker = max(
        display_width(headers["ticker"]),
        max(display_width(r["ticker"]) for r in rows),
    )
    w_pct = max(
        display_width(headers["pct"]),
        max(display_width(r["pct"]) for r in rows),
    )
    w_price = max(
        display_width(headers["price"]),
        max(display_width(r["price"]) for r in rows),
    )

    def render(t: str, p: str, pr: str, n: str, num_align_right: bool = True) -> str:
        align_pct = pad_left if num_align_right else pad_right
        align_price = pad_left if num_align_right else pad_right
        return (
            f"{pad_right(t, w_ticker)}  "
            f"{align_pct(p, w_pct)}  "
            f"{align_price(pr, w_price)}  "
            f"{n}"
        )

    lines = [
        render(
            headers["ticker"],
            headers["pct"],
            headers["price"],
            headers["name"],
        ),
    ]
    for r in rows:
        lines.append(render(r["ticker"], r["pct"], r["price"], r["name"]))
    return "\n".join(lines)


def build_message(report_path: Path, repo_url: str) -> str:
    """构造完整 Telegram HTML 消息。"""
    data = parse_report(report_path)
    title = data["title"] or "美股日报"
    date_str = data["date"]

    parts: list[str] = []
    parts.append(f"📊 <b>{html_escape(title)}</b>")
    if date_str:
        parts.append(f"📅 {html_escape(date_str)}")
    parts.append("")

    if data["gainers"]:
        parts.append("📈 <b>今日 Top 5 涨幅</b>")
        table = format_table(data["gainers"])
        parts.append(f"<pre>{html_escape(table)}</pre>")

    if data["losers"]:
        parts.append("📉 <b>今日 Top 5 跌幅</b>")
        table = format_table(data["losers"])
        parts.append(f"<pre>{html_escape(table)}</pre>")

    parts.append(f"🔗 <a href=\"{repo_url}\">查看完整日报</a>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def find_latest_report() -> Path | None:
    """优先取今日报告,否则取目录里最新的一份。"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_path = Path("reports") / f"{today}.md"
    if today_path.exists():
        return today_path
    candidates = sorted(Path("reports").glob("*.md"))
    return candidates[-1] if candidates else None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未配置,跳过推送。")
        return 0

    report = find_latest_report()
    if report is None:
        print("⚠ 找不到任何日报文件,跳过推送。")
        return 0

    repo = os.environ.get("GITHUB_REPOSITORY", "ProWD888/text")
    repo_url = f"https://github.com/{repo}/blob/main/{report.as_posix()}"

    msg = build_message(report, repo_url)
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
