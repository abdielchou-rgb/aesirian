"""文鉴 Planner — 叙事规划引擎。

从一句话创意递归展开到章节大纲。
支持英雄之旅、救猫咪、故事圈、三幕剧等叙事框架。
"""

import json
from pathlib import Path
from typing import Optional


BEAT_TEMPLATES = {
    "hero_journey": {
        "name": "英雄之旅",
        "stages": [
            "平凡世界", "冒险召唤", "拒绝召唤", "遇见导师",
            "跨越门槛", "考验/盟友/敌人", "接近核心", "严峻考验",
            "报酬", "回归之路", "复活", "带着宝物归",
        ],
        "source": "Campbell/Vogler",
    },
    "save_the_cat": {
        "name": "救猫咪",
        "stages": [
            "开场画面", "主题呈现", "铺垫", "催化剂",
            "争论", "第二幕衔接点", "B故事", "娱乐游戏",
            "中点", "坏蛋逼近", "一无所有", "灵魂黑夜",
            "第三幕衔接点", "高潮", "终场画面",
        ],
        "source": "Blake Snyder",
    },
    "story_circle": {
        "name": "故事圈",
        "stages": ["舒适区", "渴望", "陌生环境", "适应", "收获", "代价", "回归", "改变"],
        "source": "Dan Harmon",
    },
    "three_act": {
        "name": "三幕剧",
        "stages": ["第一幕：建立", "第二幕前半：对抗升级", "第二幕后半：低谷", "第三幕：高潮解决"],
        "source": "Aristotle / McKee",
    },
}


class Planner:
    """层级规划引擎 — 从一句话创意递归展开到场景。"""

    def __init__(self):
        self.templates = BEAT_TEMPLATES

    def develop_full(self, logline: str, template: str = "three_act",
                     genre: str = "xianxia_modern", target_chapters: int = 30) -> dict:
        """从一句话创意展开为完整层级规划。"""
        outline = self._expand_logline(logline, template, genre)
        acts = [self.expand_act(a) for a in outline["acts"]]
        return {
            "logline": logline,
            "template": template,
            "genre": genre,
            "outline": outline,
            "acts": acts,
            "total_chapters": sum(len(a) for a in acts),
        }

    def list_templates(self) -> list[dict]:
        return [{"id": k, "name": v["name"], "stages": len(v["stages"]), "source": v["source"]}
                for k, v in self.templates.items()]

    def _expand_logline(self, logline: str, template: str, genre: str) -> dict:
        beats = self.templates.get(template, self.templates["three_act"])
        return {
            "template": beats["name"],
            "source": beats["source"],
            "stages": beats["stages"],
            "acts": [
                {"number": i + 1, "beat": beats["stages"][i], "description": f"第{i+1}阶段：{beats['stages'][i]}",
                 "chapter_range": self._calc_chapter_range(i, len(beats["stages"]), 30)}
                for i in range(len(beats["stages"]))
            ],
        }

    def expand_act(self, act: dict) -> list[dict]:
        start_ch, end_ch = act.get("chapter_range", (1, 5))
        chapters = []
        for ci in range(start_ch, end_ch + 1):
            chapters.append({
                "chapter": ci,
                "act": act["number"],
                "act_beat": act["beat"],
                "objective": "",
                "scenes": 3,
                "end_hook": "",
            })
        return chapters

    def _calc_chapter_range(self, stage_index: int, total_stages: int, total_chapters: int) -> tuple:
        base = total_chapters // total_stages
        remainder = total_chapters % total_stages
        start = stage_index * base + min(stage_index, remainder) + 1
        end = start + base - 1 + (1 if stage_index < remainder else 0)
        return (start, end)

    def save_plan(self, plan: dict, path: str):
        Path(path).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_plan(self, path: str) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))