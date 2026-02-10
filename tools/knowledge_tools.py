"""
知识库查询 / 写入工具函数

注册为 AutoGen 工具供智能体调用，实现智能体与持久化知识库的交互。
"""
import json

from knowledge.knowledge_base import KnowledgeBase
from config import settings


def search_knowledge(keyword: str) -> str:
    """从公共知识库搜索 CSS 样式类、布局模式或编码经验。

    Args:
        keyword: 搜索关键词，如 'flex'、'grid'、'居中'、'响应式' 等

    Returns:
        匹配的知识条目（JSON 字符串），未找到时返回提示
    """
    kb = KnowledgeBase.load(settings.KNOWLEDGE_BASE_PATH)
    results = kb.search(keyword)
    if results:
        return json.dumps(results, ensure_ascii=False, indent=2)
    return "未找到相关知识条目"


def add_knowledge(category: str, name: str, description: str, code: str) -> str:
    """向公共知识库添加新的 CSS 样式类或编码经验。

    Args:
        category: 分类，可选值: css_classes, layout_patterns, coding_tips
        name: 条目名称
        description: 条目描述
        code: 相关代码示例

    Returns:
        操作结果文本
    """
    valid_categories = ("css_classes", "layout_patterns", "coding_tips")
    if category not in valid_categories:
        return f"无效分类 '{category}'，可选值: {', '.join(valid_categories)}"

    kb = KnowledgeBase.load(settings.KNOWLEDGE_BASE_PATH)
    entry = {"name": name, "description": description, "code": code}
    kb.add_entry(category, entry)
    return f"已成功添加到知识库 [{category}] 分类: {name}"


def get_knowledge_summary() -> str:
    """获取知识库的完整摘要，便于智能体了解已有的公共样式和经验。

    Returns:
        知识库的格式化文本
    """
    kb = KnowledgeBase.load(settings.KNOWLEDGE_BASE_PATH)
    return kb.get_all_as_text()
