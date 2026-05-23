"""把今日全产业链日报推送到 Telegram(多条消息,按大模块切分)。

环境变量:
  TELEGRAM_BOT_TOKEN  必填,@BotFather 给的 token
  TELEGRAM_CHAT_ID    必填,你的 chat_id(私聊或群组)
  GITHUB_REPOSITORY   选填,GitHub Actions 自动注入,用于生成"查看完整日报"链接

推送策略:
  1. 第 1 条:标题 + 今日 Top 5 涨幅 + 今日 Top 5 跌幅
  2. 之后每个大模块(上 / 中 / 下游)各发一条,内部再按子分类分块
  3. 每条消息严格控制在 4096 字符以内(Telegram 上限)

每张表 5 列:代码 / 涨跌幅 / 现价 / 公司 / 看点,
用 <pre> 等宽字体渲染,中文按 2 列宽度对齐。
数据来源是 reports/YYYY-MM-DD.csv,公司中文名和"看点"从 tickers.py 反查。
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from tickers import lookup_meta


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
# Report parsing
# --------------------------------------------------------------------------- #
def find_latest_csv() -> Path | None:
    """优先取今日 CSV,否则取目录里最新的一份。"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_path = Path("reports") / f"{today}.csv"
    if today_path.exists():
        return today_path
    candidates = sorted(Path("reports").glob("*.csv"))
    return candidates[-1] if candidates else None


def find_latest_md() -> Path | None:
    today = datetime.now().strftime("%Y-%m-%d")
    today_path = Path("reports") / f"{today}.md"
    if today_path.exists():
        return today_path
    candidates = sorted(Path("reports").glob("*.md"))
    return candidates[-1] if candidates else None


def parse_csv(csv_path: Path) -> list[dict]:
    """读 CSV,补全 (中文名, 看点),只保留有价格的行。"""
    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("error") or not r.get("price"):
                continue
            symbol = r["symbol"]
            meta = lookup_meta(symbol)
            if meta is None:
                continue
            name_cn, takeaway, sub_cat, super_cat = meta
            try:
                price = float(r["price"])
                pct = float(r["change_pct"]) if r.get("change_pct") else None
            except (ValueError, KeyError):
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": name_cn,
                    "takeaway": takeaway,
                    "sub_category": sub_cat,
                    "super_category": super_cat,
                    "price": price,
                    "pct": pct,
                }
            )
    return rows


def parse_md_title(md_path: Path) -> tuple[str, str]:
    """从 Markdown 第一行抽取标题 + 日期。"""
    text = md_path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0] if text else ""
    m = re.match(
        r"^#\s*(.*?)\s*[—–-]\s*(\d{4}-\d{2}-\d{2}.*)$", first_line.strip()
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return first_line.lstrip("#").strip() or "美股 AI 全产业链日报", ""


# --------------------------------------------------------------------------- #
# Width-aware padding (CJK = 2 cols)
# --------------------------------------------------------------------------- #
def display_width(s: str) -> int:
    """CJK/全角字符按 2 列计算,其它按 1 列。"""
    return sum(2 if ord(c) > 127 else 1 for c in s)


def pad_right(s: str, target: int) -> str:
    return s + " " * max(0, target - display_width(s))


def pad_left(s: str, target: int) -> str:
    return " " * max(0, target - display_width(s)) + s


def truncate_to_width(s: str, max_w: int) -> str:
    """按显示宽度截断字符串,超出加 …"""
    if display_width(s) <= max_w:
        return s
    out = ""
    cur = 0
    for c in s:
        w = 2 if ord(c) > 127 else 1
        if cur + w > max_w - 1:
            break
        out += c
        cur += w
    return out + "…"


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def fmt_pct(p: float | None) -> str:
    if p is None:
        return "—"
    sign = "+" if p >= 0 else ""
    return f"{sign}{p:.2f}%"


def fmt_price(p: float | None) -> str:
    if p is None:
        return "—"
    if p >= 1000:
        return f"${p:,.0f}"
    return f"${p:.2f}"


def format_table(rows: list[dict], with_takeaway: bool = True) -> str:
    """渲染等宽对齐表格。

    列: 代码 / 涨跌幅 / 现价 / 公司 [/ 看点]
    """
    if not rows:
        return ""

    # 准备每行的字段值(都已字符串化)
    items = [
        {
            "ticker": r["symbol"],
            "pct": fmt_pct(r["pct"]),
            "price": fmt_price(r["price"]),
            "name": r["name"],
            "takeaway": truncate_to_width(r.get("takeaway", ""), 26),
        }
        for r in rows
    ]

    headers = {
        "ticker": "代码",
        "pct": "涨跌幅",
        "price": "现价",
        "name": "公司",
        "takeaway": "看点",
    }

    cols = ["ticker", "pct", "price", "name"] + (["takeaway"] if with_takeaway else [])
    widths = {
        c: max(display_width(headers[c]), max(display_width(it[c]) for it in items))
        for c in cols
    }

    def render_row(values: dict) -> str:
        parts = []
        for c in cols:
            if c in ("pct", "price"):
                parts.append(pad_left(values[c], widths[c]))
            else:
                parts.append(pad_right(values[c], widths[c]))
        return "  ".join(parts).rstrip()

    out = [render_row(headers)]
    for it in items:
        out.append(render_row(it))
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Top 5 from full report
# --------------------------------------------------------------------------- #
def build_top_message(rows: list[dict], title: str, date_str: str, repo_url: str) -> str:
    valid = [r for r in rows if r["pct"] is not None]
    gainers = sorted(valid, key=lambda r: r["pct"], reverse=True)[:5]
    losers = sorted(valid, key=lambda r: r["pct"])[:5]

    parts: list[str] = []
    parts.append(f"📊 <b>{html_escape(title)}</b>")
    if date_str:
        parts.append(f"📅 {html_escape(date_str)}")
    parts.append("")

    if gainers:
        parts.append("📈 <b>今日 Top 5 涨幅</b>")
        parts.append(f"<pre>{html_escape(format_table(gainers))}</pre>")

    if losers:
        parts.append("📉 <b>今日 Top 5 跌幅</b>")
        parts.append(f"<pre>{html_escape(format_table(losers))}</pre>")

    parts.append(f"🔗 <a href=\"{repo_url}\">查看完整日报</a>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Per super-category messages
# --------------------------------------------------------------------------- #
SUPER_EMOJI = {
    "上游 · 基础设施 / 硬件": "🔹",
    "中游 · 云算力 / 平台 / 模型": "🔸",
    "下游 · 应用层": "🔷",
}


def build_super_message(super_cat: str, rows: list[dict]) -> str:
    """构造单个大模块的消息。

    内部按 sub_category 分块,每块一张 5 列表格。
    每条控制在 4000 字符内,超过会拆成多条返回。
    """
    emoji = SUPER_EMOJI.get(super_cat, "📦")
    by_sub: dict[str, list[dict]] = {}
    for r in rows:
        by_sub.setdefault(r["sub_category"], []).append(r)

    header = f"{emoji} <b>{html_escape(super_cat)}</b>"
    parts: list[str] = [header]

    for sub_cat, group in by_sub.items():
        # 当前子分类块
        sub_block = [
            "",
            f"▸ <b>{html_escape(sub_cat)}</b>",
            f"<pre>{html_escape(format_table(group))}</pre>",
        ]
        # 检查累计长度是否会爆
        candidate = "\n".join(parts + sub_block)
        if len(candidate) > 3900 and len(parts) > 1:
            # 分一条新消息(用一个特殊 marker 表示分隔)
            parts.append("\n<<<SPLIT>>>")
            parts.append(header + " (续)")
        parts.extend(sub_block)

    return "\n".join(parts)


def split_into_messages(big_msg: str) -> list[str]:
    """按 <<<SPLIT>>> 标记切成多条消息。"""
    if "<<<SPLIT>>>" not in big_msg:
        return [big_msg]
    chunks = big_msg.split("\n<<<SPLIT>>>\n")
    return [c.strip() for c in chunks if c.strip()]


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def safe_send(token: str, chat_id: str, msg: str, label: str) -> bool:
    """发送一条消息,处理截断和异常。"""
    if len(msg) > 4096:
        msg = msg[:4040] + "\n…(已截断)"
    try:
        result = send_telegram(token, chat_id, msg)
    except Exception as e:  # noqa: BLE001
        print(f"✗ {label} 推送失败: {type(e).__name__}: {e}")
        return False
    if result.get("ok"):
        print(f"✓ {label} 推送成功 (message_id={result['result']['message_id']})")
        return True
    print(f"✗ {label} 返回错误: {result}")
    return False


def main() -> int:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未配置,跳过推送。")
        return 0

    csv_path = find_latest_csv()
    md_path = find_latest_md()
    if csv_path is None or md_path is None:
        print("⚠ 找不到 CSV 或 Markdown 日报,跳过推送。")
        return 0

    repo = os.environ.get("GITHUB_REPOSITORY", "ProWD888/text")
    repo_url = f"https://github.com/{repo}/blob/main/{md_path.as_posix()}"

    rows = parse_csv(csv_path)
    if not rows:
        print("⚠ CSV 中没有有效数据,跳过推送。")
        return 0

    title, date_str = parse_md_title(md_path)

    # 1. Top 5 概览
    overview = build_top_message(rows, title, date_str, repo_url)
    safe_send(token, chat_id, overview, "概览")
    time.sleep(1)  # 避免 Telegram 反垃圾

    # 2. 每个大模块各发一条(可能拆多条)
    by_super: dict[str, list[dict]] = {}
    for r in rows:
        by_super.setdefault(r["super_category"], []).append(r)

    sent_count = 1
    fail_count = 0
    for super_cat, group in by_super.items():
        big = build_super_message(super_cat, group)
        for sub_msg in split_into_messages(big):
            ok = safe_send(token, chat_id, sub_msg, super_cat)
            if ok:
                sent_count += 1
            else:
                fail_count += 1
            time.sleep(1)

    print(f"\n📊 总结: 共发送 {sent_count} 条,失败 {fail_count} 条")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
