"""美股 AI 全产业链 ticker 分类清单(嵌套版)。

数据结构:
    TICKERS[大模块][子分类] = [(代码, 中文名, 看点), ...]

"大模块"对应产业链上 / 中 / 下游,"子分类"细化为细分赛道。
扩展方式:在对应分类的列表中追加 (symbol, name_cn, takeaway) 即可。
"""

from __future__ import annotations

TICKERS: dict[str, dict[str, list[tuple[str, str, str]]]] = {
    "上游 · 基础设施 / 硬件": {
        "AI 芯片设计": [
            ("NVDA", "英伟达", "AI GPU 绝对龙头, CUDA 生态"),
            ("AMD", "超威半导体", "MI350/400 系列, GPU+CPU 双线"),
            ("AVGO", "博通", "Google/Meta 定制 ASIC, 网络龙头"),
            ("MRVL", "美满电子", "AI ASIC, 光互连 DSP"),
            ("TSM", "台积电", "全球高端 AI 芯片代工"),
            ("ARM", "Arm 控股", "CPU IP 授权, 移动+AI 端侧"),
            ("QCOM", "高通", "端侧 AI (手机/PC/汽车)"),
            ("INTC", "英特尔", "Gaudi 加速器, 代工挑战"),
        ],
        "半导体设备 & EDA": [
            ("ASML", "阿斯麦", "EUV 光刻机独家"),
            ("AMAT", "应用材料", "沉积/刻蚀设备"),
            ("LRCX", "泛林集团", "刻蚀设备龙头"),
            ("KLAC", "科磊", "量测设备"),
            ("SNPS", "Synopsys", "EDA 三巨头"),
            ("CDNS", "Cadence", "EDA 三巨头"),
        ],
        "存储 / 互联 / 光模块": [
            ("MU", "美光", "HBM 高带宽内存核心"),
            ("ANET", "Arista", "数据中心高速交换机"),
            ("CIEN", "Ciena", "光通信"),
            ("COHR", "Coherent", "光模块/激光"),
            ("ALAB", "Astera Labs", "AI 互连小盘"),
            ("CRDO", "Credo", "SerDes/AEC 高速互联"),
            ("VRT", "Vertiv", "数据中心电源/液冷"),
            ("DELL", "戴尔", "AI 服务器代工"),
        ],
        "AI 电力链": [
            ("GEV", "GE Vernova", "燃气轮机+电网"),
            ("CEG", "Constellation", "美最大核电运营商"),
            ("VST", "Vistra", "核电+天然气"),
            ("ETN", "Eaton", "电气元件/数据中心"),
            ("PWR", "Quanta Services", "电网建设承包"),
            ("OKLO", "Oklo", "小型核反应堆 SMR"),
        ],
    },
    "中游 · 云算力 / 平台 / 模型": {
        "超大规模云厂商": [
            ("MSFT", "微软", "Azure + OpenAI 深度绑定"),
            ("GOOGL", "谷歌", "Gemini + TPU 自研"),
            ("AMZN", "亚马逊", "AWS + Bedrock + Trainium"),
            ("META", "Meta", "Llama + 自研 MTIA 芯片"),
            ("ORCL", "甲骨文", "OCI + OpenAI 大单"),
            ("IBM", "IBM", "watsonx 企业 AI"),
        ],
        "数据中心 REIT": [
            ("EQIX", "Equinix", "全球互联型数据中心"),
            ("DLR", "Digital Realty", "大型数据中心 REIT"),
            ("IRM", "Iron Mountain", "数据中心+存储"),
        ],
        "数据 / AI 平台": [
            ("SNOW", "Snowflake", "数据云 + Cortex AI"),
            ("PLTR", "Palantir", "AIP 企业 AI 平台"),
            ("MDB", "MongoDB", "向量数据库能力"),
            ("DDOG", "Datadog", "AI 监控/可观测性"),
            ("ESTC", "Elastic", "搜索+向量"),
            ("AI", "C3.ai", "企业 AI 应用平台"),
        ],
    },
    "下游 · 应用层": {
        "通用 SaaS + AI Copilot": [
            ("CRM", "Salesforce", "Agentforce AI Agent"),
            ("ADBE", "Adobe", "Firefly 生成式设计"),
            ("NOW", "ServiceNow", "企业流程 AI Agent"),
            ("INTU", "Intuit", "财税 AI"),
            ("WDAY", "Workday", "HR/财务 AI"),
            ("HUBS", "HubSpot", "营销 AI"),
        ],
        "互联网 / 广告 / 内容": [
            ("APP", "AppLovin", "AI 广告投放 (暴涨股)"),
            ("NFLX", "奈飞", "推荐算法"),
            ("SPOT", "Spotify", "AI DJ / 推荐"),
            ("RDDT", "Reddit", "数据被 LLM 训练"),
        ],
        "自驾 / 机器人 / 物理 AI": [
            ("TSLA", "特斯拉", "FSD + Optimus + Dojo"),
            ("UBER", "Uber", "Robotaxi 平台合作"),
            ("MBLY", "Mobileye", "ADAS 芯片+方案"),
            ("SYM", "Symbotic", "仓储机器人"),
            ("ISRG", "直觉外科", "手术机器人"),
        ],
        "行业 AI": [
            ("CRWD", "CrowdStrike", "AI 网络安全"),
            ("PANW", "Palo Alto", "AI 安全"),
            ("S", "SentinelOne", "AI 端点安全"),
            ("TEM", "Tempus AI", "精准医疗"),
            ("VEEV", "Veeva", "医药 SaaS"),
        ],
    },
}


def all_tickers() -> list[tuple[str, str, str, str]]:
    """返回 (symbol, description, sub_category, super_category) 四元组列表。

    description 字段格式为 '中文名 — 看点',与旧版 tracker.py 兼容。
    """
    out: list[tuple[str, str, str, str]] = []
    for super_cat, sub_cats in TICKERS.items():
        for sub_cat, items in sub_cats.items():
            for sym, name_cn, takeaway in items:
                desc = f"{name_cn} — {takeaway}"
                out.append((sym, desc, sub_cat, super_cat))
    return out


def lookup_meta(symbol: str) -> tuple[str, str, str, str] | None:
    """按 ticker 反查 (中文名, 看点, 子分类, 大模块)。"""
    for super_cat, sub_cats in TICKERS.items():
        for sub_cat, items in sub_cats.items():
            for sym, name_cn, takeaway in items:
                if sym == symbol:
                    return (name_cn, takeaway, sub_cat, super_cat)
    return None
