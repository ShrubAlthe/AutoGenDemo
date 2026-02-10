"""
Figma 分析相关数据类 — 与智能体解耦，独立存放
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class DesignInput:
    """用户输入的设计稿信息"""

    pc_link: str
    pc_node_id: Optional[str] = None
    mobile_link: Optional[str] = None
    mobile_node_id: Optional[str] = None


@dataclass
class LayoutInfo:
    """单个区块的布局分析信息"""

    layout_type: str                               # flex / grid / absolute / block
    direction: str = "row"                         # row / column
    sections: List[Dict[str, Any]] = field(default_factory=list)
    responsive: bool = False
    notes: str = ""


@dataclass
class ComponentInfo:
    """设计稿中的组件信息"""

    name: str
    node_id: str
    component_type: str                            # button / input / card / ...
    styles: Dict[str, Any] = field(default_factory=dict)
    children: List["ComponentInfo"] = field(default_factory=list)


@dataclass
class FigmaAnalysisResult:
    """Figma 分析智能体输出的完整分析结果"""

    pc_layout: Optional[LayoutInfo] = None
    mobile_layout: Optional[LayoutInfo] = None
    components: List[ComponentInfo] = field(default_factory=list)
    styles: Dict[str, Any] = field(default_factory=dict)
    color_palette: List[str] = field(default_factory=list)
    fonts: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""
