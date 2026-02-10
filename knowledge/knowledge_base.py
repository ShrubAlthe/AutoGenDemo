"""
持久化公共知识库管理器

使用 JSON 文件存储，按分类索引（css_classes / layout_patterns / coding_tips）。
提供 search / add_entry / get_by_category 等方法，供智能体通过工具函数调用。
"""
import json
import os
from typing import Any, Dict, List


class KnowledgeBase:
    """公共知识库 — CRUD + 关键词检索"""

    # 默认分类列表
    DEFAULT_CATEGORIES = ("css_classes", "layout_patterns", "coding_tips")

    def __init__(self, data: Dict[str, List[Any]], file_path: str) -> None:
        self._data = data
        self._file_path = file_path

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, file_path: str) -> "KnowledgeBase":
        """从 JSON 文件加载知识库；若文件不存在则创建空库。"""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {cat: [] for cat in cls.DEFAULT_CATEGORIES}
        return cls(data, file_path)

    def save(self) -> None:
        """将知识库持久化到 JSON 文件。"""
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """按关键词搜索所有分类，返回匹配的条目列表。"""
        results: List[Dict[str, Any]] = []
        keyword_lower = keyword.lower()
        for category, entries in self._data.items():
            for entry in entries:
                entry_str = json.dumps(entry, ensure_ascii=False).lower()
                if keyword_lower in entry_str:
                    results.append({"category": category, **entry})
        return results

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类获取所有条目。"""
        return self._data.get(category, [])

    def get_all_as_text(self) -> str:
        """将整个知识库格式化为可阅读文本（供嵌入 prompt）。"""
        lines: List[str] = []
        for category, entries in self._data.items():
            lines.append(f"\n## {category}")
            for entry in entries:
                lines.append(json.dumps(entry, ensure_ascii=False))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add_entry(self, category: str, content: Dict[str, Any]) -> None:
        """向指定分类添加一条新记录，并自动持久化。"""
        if category not in self._data:
            self._data[category] = []
        self._data[category].append(content)
        self.save()
