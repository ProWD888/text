"""美股 AI 全产业链行情追踪器。

抓取每只 ticker 的实时价格、涨跌幅、市值、PE、52 周区间,
并生成:
  1. 终端表格(rich)
  2. Markdown 日报(reports/YYYY-MM-DD.md)
  3. CSV 数据快照(reports/YYYY-MM-DD.csv)

用法:
    python tracker.py                  # 全量抓取并输出报告
    python tracker.py --no-table       # 只生成文件,不打印终端表格
    python tracker.py --out my_reports # 指定输出目录
"""

from __future__ import annotations

import argparse
import csv
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import yfinance as yf
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from tickers import TICKERS, all_tickers

# 抑制 yfinance 在抓取空数据时的噪音日志
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

console = Console()


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class TickerSnapshot:
    symbol: str
    name: str
    category: str            # 子分类(细分赛道)
    super_category: str      # 大模块(上 / 中 / 下游)
    description: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    volume: Optional[int] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def fetch_one(
    symbol: str, description: str, category: str, super_category: str
) -> TickerSnapshot:
    """抓取单只标的的快照。失败时把异常记录到 snapshot.error。"""
    snap = TickerSnapshot(
        symbol=symbol,
        name=symbol,
        category=category,
        super_category=super_category,
        description=description,
    )
    try:
        t = yf.Ticker(symbol)
        info = t.info or {}

        snap.name = info.get("shortName") or info.get("longName") or symbol
        snap.price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        if snap.price and prev_close:
            snap.change_pct = (snap.price - prev_close) / prev_close * 100

        snap.market_cap = info.get("marketCap")
        snap.pe_ratio = info.get("trailingPE")
        snap.forward_pe = info.get("forwardPE")
        snap.volume = info.get("regularMarketVolume") or info.get("volume")
        snap.fifty_two_week_high = info.get("fiftyTwoWeekHigh")
        snap.fifty_two_week_low = info.get("fiftyTwoWeekLow")

        # 价格仍为空时,尝试从最近一根 K 线兜底
        if snap.price is None:
            hist = t.history(period="5d")
            if len(hist) > 0:
                snap.price = float(hist["Close"].iloc[-1])
                if len(hist) > 1:
                    prev = float(hist["Close"].iloc[-2])
                    snap.change_pct = (snap.price - prev) / prev * 100

        # 仍然没有价格 → 标记为失败(常见于已退市/低流动性 OTC)
        if snap.price is None:
            snap.error = "no price data (delisted or illiquid)"
    except Exception as e:  # noqa: BLE001
        snap.error = f"{type(e).__name__}: {e}"
    return snap


def fetch_all(max_workers: int = 10) -> list[TickerSnapshot]:
    """并发抓取所有 ticker。"""
    items = all_tickers()
    snaps: list[TickerSnapshot] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Fetching"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("fetch", total=len(items))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {
                ex.submit(fetch_one, sym, desc, sub_cat, super_cat): sym
                for sym, desc, sub_cat, super_cat in items
            }
            for fut in as_completed(futures):
                snaps.append(fut.result())
                progress.update(task, advance=1)

    # 按嵌套分类原始顺序 + ticker 字母排序
    super_order: dict[str, int] = {c: i for i, c in enumerate(TICKERS)}
    sub_order: dict[tuple[str, str], int] = {}
    for i, super_cat in enumerate(TICKERS):
        for j, sub_cat in enumerate(TICKERS[super_cat]):
            sub_order[(super_cat, sub_cat)] = i * 100 + j

    def sort_key(s: TickerSnapshot) -> tuple:
        sup = super_order.get(s.super_category, 99)
        sub = sub_order.get((s.super_category, s.category), 99)
        return (sup, sub, s.symbol)

    snaps.sort(key=sort_key)
    return snaps


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def fmt_market_cap(cap: Optional[float]) -> str:
    if cap is None or cap == 0:
        return "—"
    if cap >= 1e12:
        return f"${cap / 1e12:.2f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.2f}B"
    if cap >= 1e6:
        return f"${cap / 1e6:.2f}M"
    return f"${cap:,.0f}"


def fmt_pct(pct: Optional[float]) -> str:
    if pct is None:
        return "—"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def fmt_price(p: Optional[float]) -> str:
    return f"${p:.2f}" if p is not None else "—"


def fmt_pe(pe: Optional[float]) -> str:
    return f"{pe:.1f}" if pe and pe > 0 else "—"


def fmt_range(low: Optional[float], high: Optional[float]) -> str:
    if low is None or high is None:
        return "—"
    return f"{low:.0f}–{high:.0f}"


# --------------------------------------------------------------------------- #
# Render to terminal
# --------------------------------------------------------------------------- #
def render_table(snaps: list[TickerSnapshot]) -> None:
    by_super: dict[str, dict[str, list[TickerSnapshot]]] = {}
    for s in snaps:
        by_super.setdefault(s.super_category, {}).setdefault(s.category, []).append(s)

    for super_cat, sub_cats in by_super.items():
        console.print(f"\n[bold magenta on white] {super_cat} [/bold magenta on white]")
        for sub_cat, group in sub_cats.items():
            table = Table(
                title=sub_cat,
                header_style="bold cyan",
                title_style="bold yellow",
            )
            table.add_column("Ticker", style="bold")
            table.add_column("公司")
            table.add_column("Price", justify="right")
            table.add_column("Δ%", justify="right")
            table.add_column("Mkt Cap", justify="right")
            table.add_column("P/E", justify="right")
            table.add_column("Fwd P/E", justify="right")
            table.add_column("52W Range", justify="right")

            for s in group:
                if s.error:
                    table.add_row(
                        s.symbol,
                        s.description[:40],
                        "[red]ERROR[/red]",
                        "",
                        "",
                        "",
                        "",
                        s.error[:30],
                    )
                    continue
                color = "green" if (s.change_pct or 0) >= 0 else "red"
                change_str = f"[{color}]{fmt_pct(s.change_pct)}[/{color}]"
                table.add_row(
                    s.symbol,
                    s.description[:40],
                    fmt_price(s.price),
                    change_str,
                    fmt_market_cap(s.market_cap),
                    fmt_pe(s.pe_ratio),
                    fmt_pe(s.forward_pe),
                    fmt_range(s.fifty_two_week_low, s.fifty_two_week_high),
                )
            console.print(table)
        console.print()


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #
def write_markdown(snaps: list[TickerSnapshot], out_path: Path) -> None:
    now = datetime.now()
    lines: list[str] = [
        f"# 美股 AI 全产业链日报 — {now.strftime('%Y-%m-%d %H:%M')}",
        "",
        "> 数据来源:Yahoo Finance (yfinance)。仅供参考,不构成投资建议。",
        "",
    ]

    valid = [s for s in snaps if not s.error and s.change_pct is not None]
    if valid:
        gainers = sorted(valid, key=lambda s: s.change_pct or 0, reverse=True)[:5]
        losers = sorted(valid, key=lambda s: s.change_pct or 0)[:5]

        lines += [
            "## 今日 Top 5 涨幅",
            "",
            "| Ticker | 公司 | 涨跌幅 | 现价 |",
            "|---|---|---|---|",
        ]
        for s in gainers:
            lines.append(
                f"| **{s.symbol}** | {s.description} | "
                f"{fmt_pct(s.change_pct)} | {fmt_price(s.price)} |"
            )

        lines += [
            "",
            "## 今日 Top 5 跌幅",
            "",
            "| Ticker | 公司 | 涨跌幅 | 现价 |",
            "|---|---|---|---|",
        ]
        for s in losers:
            lines.append(
                f"| **{s.symbol}** | {s.description} | "
                f"{fmt_pct(s.change_pct)} | {fmt_price(s.price)} |"
            )
        lines.append("")

    # 按 (super_category, category) 嵌套分组
    by_super: dict[str, dict[str, list[TickerSnapshot]]] = {}
    for s in snaps:
        by_super.setdefault(s.super_category, {}).setdefault(s.category, []).append(s)

    for super_cat, sub_cats in by_super.items():
        lines += [f"## {super_cat}", ""]
        for sub_cat, group in sub_cats.items():
            lines += [
                f"### {sub_cat}",
                "",
                "| Ticker | 公司 | 现价 | 涨跌幅 | 市值 | P/E (TTM) | Fwd P/E | 52周区间 |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for s in group:
                if s.error:
                    lines.append(
                        f"| {s.symbol} | {s.description} | — | — | — | — | — | error |"
                    )
                    continue
                lines.append(
                    f"| **{s.symbol}** | {s.description} | "
                    f"{fmt_price(s.price)} | {fmt_pct(s.change_pct)} | "
                    f"{fmt_market_cap(s.market_cap)} | "
                    f"{fmt_pe(s.pe_ratio)} | {fmt_pe(s.forward_pe)} | "
                    f"{fmt_range(s.fifty_two_week_low, s.fifty_two_week_high)} |"
                )
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(snaps: list[TickerSnapshot], out_path: Path) -> None:
    fields = [
        "super_category",
        "category",
        "symbol",
        "name",
        "description",
        "price",
        "change_pct",
        "market_cap",
        "pe_ratio",
        "forward_pe",
        "volume",
        "fifty_two_week_high",
        "fifty_two_week_low",
        "error",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in snaps:
            row = {k: v for k, v in asdict(s).items() if k in fields}
            writer.writerow(row)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="美股 AI 全产业链行情追踪器"
    )
    parser.add_argument(
        "--out", default="reports", help="输出目录(默认 ./reports)"
    )
    parser.add_argument(
        "--no-table", action="store_true", help="不在终端打印表格"
    )
    parser.add_argument(
        "--workers", type=int, default=10, help="并发抓取线程数(默认 10)"
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    snaps = fetch_all(max_workers=args.workers)

    if not args.no_table:
        render_table(snaps)

    today = datetime.now().strftime("%Y-%m-%d")
    md_path = out_dir / f"{today}.md"
    csv_path = out_dir / f"{today}.csv"
    write_markdown(snaps, md_path)
    write_csv(snaps, csv_path)

    n_ok = sum(1 for s in snaps if not s.error)
    n_err = sum(1 for s in snaps if s.error)
    console.print(
        f"\n[bold green]✓[/bold green] 共 {len(snaps)} 只,"
        f"成功 {n_ok},失败 {n_err}"
    )
    console.print(f"[green]→ Markdown:[/green] {md_path}")
    console.print(f"[green]→ CSV:    [/green] {csv_path}")


if __name__ == "__main__":
    main()
