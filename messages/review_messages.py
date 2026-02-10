"""
结果审核相关数据类 — 与智能体解耦，独立存放
"""
from dataclasses import dataclass


@dataclass
class ScreenshotCompareResult:
    """截图对比结果"""

    similarity: float = 0.0       # 0‑1 之间的相似度分数
    passed: bool = False          # 是否达到阈值
    figma_screenshot: str = ""    # Figma 截图文件路径
    browser_screenshot: str = ""  # 浏览器截图文件路径
    details: str = ""             # 差异分析文本
