"""人形机器人产业链 ticker 分类清单。

每个 ticker 都附带中文描述,便于在终端和报告中显示。
扩展方式:在对应分类的列表中追加 (symbol, description) 即可。
"""

from __future__ import annotations

TICKERS: dict[str, list[tuple[str, str]]] = {
    "整机本体 (OEM)": [
        ("TSLA", "Tesla — Optimus 量产"),
        ("HMC", "Honda — Asimo 后继研究"),
        ("HYMTF", "Hyundai — Boston Dynamics 母公司 (OTC)"),
        ("TM", "Toyota — 与 BD 合作 / T-HR3"),
    ],
    "AI 芯片 / 大脑": [
        ("NVDA", "NVIDIA — Isaac/GROOT/Jetson Thor"),
        ("QCOM", "Qualcomm — RB6/RB7 机器人平台"),
        ("AMD", "AMD — Versal 自适应 SoC"),
        ("AVGO", "Broadcom — 定制 ASIC"),
    ],
    "传感器 / 视觉": [
        ("AAPL", "Apple — LiDAR 自研"),
        ("MBLY", "Mobileye — 视觉 SoC"),
        ("TER", "Teradyne — UR/MiR 协作机器人"),
        ("ADI", "Analog Devices — IMU"),
        ("TXN", "Texas Instruments — 模拟/电源 IC"),
        ("ON", "ON Semi — 图像传感器"),
        ("TTDKY", "TDK ADR — 力矩传感器"),
    ],
    "执行器 / 电机 / 减速器": [
        ("AME", "Ametek — 高精度伺服电机"),
        ("ROK", "Rockwell Automation"),
        ("ABBNY", "ABB ADR — 机器人电机/驱动"),
        ("PH", "Parker Hannifin — 运动控制"),
        ("EMR", "Emerson — 控制系统"),
        ("ETN", "Eaton — 电气元件"),
        ("RBC", "Regal Rexnord — 电机+轴承"),
        ("HLIO", "Helios Tech — 运动控制小盘"),
        ("FF", "Schaeffler ADR — 减速器/轴承"),
    ],
    "代工 / 制造": [
        ("FXCNY", "Foxconn ADR — Figure AI 代工"),
        ("JBL", "Jabil"),
        ("FLEX", "Flex"),
    ],
    "下游客户": [
        ("AMZN", "Amazon — 仓储部署"),
        ("WMT", "Walmart — 物流测试"),
        ("F", "Ford"),
        ("GM", "General Motors"),
        ("UPS", "UPS"),
        ("FDX", "FedEx"),
    ],
    "主题 ETF": [
        ("KOID", "Themes Humanoid Robotics — 唯一纯人形 ETF"),
        ("BOTZ", "Global X Robotics & AI"),
        ("ROBO", "ROBO Global Robotics"),
        ("IRBO", "iShares Robotics & AI"),
        ("ARKQ", "ARK Autonomous & Robotics"),
    ],
}


def all_tickers() -> list[tuple[str, str, str]]:
    """返回 (symbol, description, category) 三元组列表。"""
    out: list[tuple[str, str, str]] = []
    for category, items in TICKERS.items():
        for symbol, desc in items:
            out.append((symbol, desc, category))
    return out
