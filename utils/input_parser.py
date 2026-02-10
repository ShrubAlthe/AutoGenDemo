"""
多格式输入参数解析器

支持两种输入格式：
  格式 A: python main.py <pc_link> <mobile_link>
  格式 B: python main.py <pc_link> <pc_node_id> <mobile_link> <mobile_node_id>

也支持仅传入单个 PC 端链接。
"""
import re
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class DesignInput:
    """解析后的设计稿输入参数"""

    pc_link: str
    pc_node_id: Optional[str] = None
    mobile_link: Optional[str] = None
    mobile_node_id: Optional[str] = None

    # ------------------------------------------------------------------
    # 从链接中提取信息
    # ------------------------------------------------------------------

    @property
    def pc_file_key(self) -> Optional[str]:
        """从 PC 端链接提取 Figma file_key。"""
        return self._extract_file_key(self.pc_link)

    @property
    def mobile_file_key(self) -> Optional[str]:
        """从手机端链接提取 Figma file_key。"""
        if self.mobile_link:
            return self._extract_file_key(self.mobile_link)
        return None

    @staticmethod
    def _extract_file_key(link: str) -> Optional[str]:
        """从 Figma URL 中提取 file_key。"""
        # 支持 /design/ 和 /file/ 两种路径格式
        match = re.search(r"figma\.com/(?:design|file)/([a-zA-Z0-9]+)", link)
        return match.group(1) if match else None

    @staticmethod
    def _extract_node_id_from_link(link: str) -> Optional[str]:
        """从 Figma URL 的 query string 中提取 node-id。"""
        match = re.search(r"node-id=([0-9]+-[0-9]+)", link)
        if match:
            # Figma node id 使用冒号分隔（如 1:2），URL 中使用连字符（如 1-2）
            return match.group(1).replace("-", ":")
        return None

    # ------------------------------------------------------------------
    # 获取最终 node_id（显式参数优先，URL 中的作为回退）
    # ------------------------------------------------------------------

    def get_pc_node_id(self) -> Optional[str]:
        """获取 PC 端节点 ID。"""
        if self.pc_node_id:
            return self.pc_node_id
        return self._extract_node_id_from_link(self.pc_link)

    def get_mobile_node_id(self) -> Optional[str]:
        """获取手机端节点 ID。"""
        if self.mobile_node_id:
            return self.mobile_node_id
        if self.mobile_link:
            return self._extract_node_id_from_link(self.mobile_link)
        return None


def parse_args(args: list[str] | None = None) -> DesignInput:
    """解析命令行参数，返回 DesignInput 实例。

    Args:
        args: 参数列表，默认使用 sys.argv[1:]

    Raises:
        ValueError: 参数数量不符合要求时抛出

    Returns:
        DesignInput 实例
    """
    if args is None:
        args = sys.argv[1:]

    usage = (
        "用法:\n"
        "  格式A: python main.py <pc端链接> <手机端链接>\n"
        "  格式B: python main.py <pc端链接> <pc端节点ID> <手机端链接> <手机端节点ID>\n"
        "  仅PC:  python main.py <pc端链接>"
    )

    if len(args) == 0:
        raise ValueError(f"请提供设计稿参数:\n{usage}")

    if len(args) == 1:
        # 仅 PC 端链接
        return DesignInput(pc_link=args[0])

    if len(args) == 2:
        # 格式 A: PC 端链接 + 手机端链接
        return DesignInput(pc_link=args[0], mobile_link=args[1])

    if len(args) == 4:
        # 格式 B: PC 端链接 + PC 端节点 ID + 手机端链接 + 手机端节点 ID
        return DesignInput(
            pc_link=args[0],
            pc_node_id=args[1],
            mobile_link=args[2],
            mobile_node_id=args[3],
        )

    raise ValueError(f"不支持的参数数量 ({len(args)}):\n{usage}")
