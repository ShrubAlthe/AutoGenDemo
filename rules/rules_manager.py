"""
规则管理器

维护两类规则文件：
- global_rules.json : 所有智能体必须遵守的硬性规则，注入每个智能体的 system_message
- coding_rules.json : 编码规范，代码审核智能体专用

支持在运行时将用户纠正点追加到 global_rules.json。
"""
import json
import os
from typing import Dict, List


class RulesManager:
    """规则加载 / 查询 / 动态追加"""

    def __init__(self, global_rules_path: str, coding_rules_path: str) -> None:
        self._global_rules_path = global_rules_path
        self._coding_rules_path = coding_rules_path
        self._global_rules: Dict = self._load_json(global_rules_path)
        self._coding_rules: Dict = self._load_json(coding_rules_path)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: str) -> dict:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_json(self, data: dict, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_global_rules(self) -> List[str]:
        """返回全局规则 + 用户纠正点的完整列表。"""
        rules = self._global_rules.get("rules", [])
        corrections = self._global_rules.get("user_corrections", [])
        return rules + corrections

    def get_coding_rules(self) -> Dict:
        """返回编码规范的完整字典。"""
        return self._coding_rules

    def get_rules_prompt(self) -> str:
        """生成全局规则提示文本，用于注入智能体 system_message。"""
        rules = self.get_global_rules()
        rules_text = "\n".join([f"  {i + 1}. {r}" for i, r in enumerate(rules)])
        return (
            "【强制规则 — 任何情况下都不允许违反】\n"
            f"{rules_text}\n\n"
            "违反以上任何一条规则都将导致代码审核失败。"
        )

    def get_coding_rules_prompt(self) -> str:
        """生成编码规范提示文本，供代码审核智能体使用。"""
        lines: List[str] = ["【编码规范】"]
        for category, rules in self._coding_rules.items():
            lines.append(f"\n{category}:")
            if isinstance(rules, list):
                for rule in rules:
                    lines.append(f"  - {rule}")
            else:
                lines.append(f"  - {rules}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add_user_correction(self, correction: str) -> None:
        """将用户纠正点追加到全局规则，并持久化。"""
        if "user_corrections" not in self._global_rules:
            self._global_rules["user_corrections"] = []
        self._global_rules["user_corrections"].append(correction)
        self._save_json(self._global_rules, self._global_rules_path)

    # ------------------------------------------------------------------
    # 热重载
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """重新从磁盘加载规则（用于外层循环每轮开始前）。"""
        self._global_rules = self._load_json(self._global_rules_path)
        self._coding_rules = self._load_json(self._coding_rules_path)
