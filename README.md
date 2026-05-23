# 人形机器人产业链行情追踪器

一个轻量 Python 脚本,自动抓取美股**人形机器人产业链**全部标的的实时行情、PE、市值,并生成每日报告(Markdown + CSV)。

## 功能

- 📡 **实时抓取**:基于 [yfinance](https://github.com/ranaroussi/yfinance) 拉取 Yahoo Finance 数据,无需 API key
- 🗂 **产业链分类**:整机本体 / AI 芯片 / 传感器 / 执行器 / 代工 / 下游客户 / 主题 ETF
- 📊 **多种输出**:
  - 终端彩色表格(rich)
  - Markdown 日报(含 Top 5 涨跌幅榜)
  - CSV 数据快照(便于 Excel/pandas 后续分析)
- ⚡ **并发抓取**:默认 10 线程,~40 只票几秒搞定
- 🛠 **易扩展**:在 `tickers.py` 中追加 `(symbol, description)` 即可

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python tracker.py

# 3. 查看结果
ls reports/
# reports/2026-05-22.md
# reports/2026-05-22.csv
```

## 命令行参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--out DIR` | `reports` | 输出目录 |
| `--no-table` | False | 不在终端打印表格(只写文件) |
| `--workers N` | 10 | 并发抓取线程数 |

## 标的清单

清单维护在 `tickers.py`,当前覆盖 7 大类约 40 只标的。新增方法:

```python
TICKERS = {
    "你的新分类": [
        ("AAPL", "Apple — 备注信息"),
        ...
    ],
}
```

## 定时跑(可选)

```bash
# 每个交易日收盘后 1 小时跑一次(美东 17:00)
0 17 * * 1-5 cd /path/to/text && /usr/bin/python tracker.py
```

## 输出示例

终端:

```
                整机本体 (OEM)
┏━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━┓
┃ Ticker   ┃ 公司          ┃ Price ┃ Δ%     ┃ Mkt Cap  ┃ P/E ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━┩
│ TSLA     │ Tesla         │ ...   │ +1.23% │ ...      │ ... │
└──────────┴───────────────┴───────┴────────┴──────────┴─────┘
```

Markdown 报告:

```
# 人形机器人产业链日报 — 2026-05-22 14:30

## 今日 Top 5 涨幅
...
## 整机本体 (OEM)
| Ticker | 公司 | 现价 | 涨跌幅 | 市值 | P/E (TTM) | Fwd P/E | 52周区间 |
| --- | --- | --- | --- | --- | --- | --- | --- |
...
```

## 注意事项

- Yahoo Finance 数据有延迟(通常 15 分钟),不适合做高频交易
- yfinance 偶尔会因 Yahoo 反爬被限流,失败的票会在报告里标注 `error`
- 仅供参考,**不构成投资建议**

## 许可

MIT
