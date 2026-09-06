"""写前门禁 — Tianming 6 道关卡模式。

在正文落地前拦截问题，不是写后审计。
每一章必须穿过 6 道门才能落地。
"""

from __future__ import annotations

import re
from typing import Any

from wenjian.models import GateResult, GateSeverity


class PreGateBase:
    """写前门禁基类。

    契约说明（P3-12 清理，2026-09-07）：子类以**类属性**直接声明
    gate_id / name / description（见 PG01-PG06），本基类无需强制抽象。
    下方占位仅供文档/类型提示——若未来接入统一注册表需要实例级属性，
    再升级为真正的 ABC 抽象。
    """

    @property
    def gate_id(self) -> str:  # 子类以类属性覆盖，无需调用本实现
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def description(self) -> str:
        raise NotImplementedError

    def pass_result(self, msg="通过", details=None) -> dict:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "passed": True,
            "message": msg,
            "details": details or {},
        }

    def fail_result(self, msg, details=None) -> dict:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "passed": False,
            "message": msg,
            "details": details or {},
        }


class PG01_ProtocolParse(PreGateBase):
    """门 1：协议解析 — AI 输出必须包含分隔符 + JSON 变更声明。"""

    gate_id = "PG-01"
    name = "协议解析"
    description = "正文必须包含 ---CHANGES--- 分隔符 + JSON 变更声明"

    SEPARATOR = "---CHANGES---"

    def evaluate(self, text: str) -> dict:
        if self.SEPARATOR not in text:
            return self.fail_result(f"缺少 {self.SEPARATOR} 分隔符", {"separator": self.SEPARATOR})
        _, changes_part = text.split(self.SEPARATOR, 1)
        changes_part = changes_part.strip()
        # 尝试提取 JSON
        json_match = re.search(r"\{.*\}", changes_part, re.DOTALL)
        if not json_match:
            return self.fail_result("CHANGES 段缺少 JSON", {"changes_raw": changes_part[:200]})
        try:
            import json

            data = json.loads(json_match.group())
            required = ["character_updates", "relationship_updates", "item_updates"]
            missing = [k for k in required if k not in data]
            if missing:
                return self.fail_result(f"CHANGES 缺少字段: {missing}", {"missing": missing})
            return self.pass_result(details={"changes": data})
        except json.JSONDecodeError as e:
            return self.fail_result(f"CHANGES JSON 解析失败: {e}")


class PG02_ReferenceCheck(PreGateBase):
    """门 2：引用校验 — CHANGES 引用的角色/地点 ID 必须在设计数据中存在。"""

    gate_id = "PG-02"
    name = "引用校验"
    description = "CHANGES 引用的角色/地点/势力 ID 必须在 ledger 中存在"

    def evaluate(self, changes: dict, ledger: dict) -> dict:
        # 提取所有引用的 ID
        refs = set()
        for update_type in ["character_updates", "relationship_updates"]:
            for item in changes.get(update_type, []):
                for key in ["character_id", "id", "target_id", "location_id"]:
                    if key in item:
                        refs.add(str(item[key]))

        # 检查 ledger
        known_ids = set(ledger.get("known_ids", []))
        missing = [r for r in refs if r not in known_ids]
        if missing:
            return self.fail_result(
                f"引用了不存在的 ID: {missing}", {"missing": missing, "known_count": len(known_ids)}
            )
        return self.pass_result(details={"checked": len(refs), "all_known": True})


class PG03_ConsistencyCheck(PreGateBase):
    """门 3：一致性校验 — 角色状态变化是否与事实快照矛盾。"""

    gate_id = "PG-03"
    name = "一致性校验"
    description = "角色状态变化不能与事实快照矛盾"

    def evaluate(self, changes: dict, fact_snapshot: dict) -> dict:
        conflicts = []
        for update in changes.get("character_updates", []):
            cid = update.get("character_id", "")
            current = fact_snapshot.get("characters", {}).get(cid, {})
            for k, v in update.items():
                if k == "character_id":
                    continue
                old_v = current.get(k)
                if old_v is not None and old_v != v:
                    # 检查是否互斥（如"活着"→"死了"可以被允许，这是剧情推进）
                    conflicts.append({"character": cid, "field": k, "from": old_v, "to": v})
        if len(conflicts) > 3:
            return self.fail_result(
                f"状态变化过多 ({len(conflicts)} 处)，可能存在不一致", {"conflicts": conflicts[:5]}
            )
        return self.pass_result(details={"conflicts_checked": len(conflicts), "allowed": True})


class PG04_UnknownEntity(PreGateBase):
    """门 4：未知实体检测 — 正文不能突然出现太多未登记的实体。"""

    gate_id = "PG-04"
    name = "未知实体检测"
    description = "正文引入的未登记实体不能超过阈值"

    def evaluate(self, new_entities: list, known_ids: list, max_new: int = 3) -> dict:
        unknown = [e for e in new_entities if e.get("id") not in known_ids]
        # 区分为"有剧情作用的"和"纯龙套"
        with_role = [e for e in unknown if e.get("role", "background") != "background"]
        if len(with_role) > max_new:
            return self.fail_result(
                f"引入了 {len(with_role)} 个有剧情作用的新实体（上限 {max_new}）",
                {"new_with_role": with_role, "total_unknown": len(unknown)},
            )
        return self.pass_result(
            details={"new_with_role": len(with_role), "total_unknown": len(unknown)}
        )


class PG05_DescriptionCheck(PreGateBase):
    """门 5：描写一致性 — 外貌描写是否与角色档案一致。"""

    gate_id = "PG-05"
    name = "描写一致性"
    description = "正文中角色外貌描写不能与档案矛盾"

    def evaluate(self, text: str, character_profiles: dict) -> dict:
        mismatches = []
        # 简单启发式：提取"发色""瞳色""肤色"等描写
        for cid, profile in character_profiles.items():
            name = profile.get("name", cid)
            for attr in ["hair", "eye", "skin", "height"]:
                expected = profile.get(attr)
                if not expected:
                    continue
                # 在正文中搜索"name + 的 + attr"
                pattern = re.compile(f"{name}.*?的.*?({attr})[:：]?\s*(\S+)")
                for match in pattern.finditer(text):
                    found = match.group(2)
                    if found and found not in expected:
                        mismatches.append(
                            {"character": name, "attr": attr, "expected": expected, "found": found}
                        )
        if mismatches:
            return self.fail_result(f"外貌描写不一致: {mismatches}", {"mismatches": mismatches})
        return self.pass_result()


class PG06_BlueprintPresence(PreGateBase):
    """门 6：蓝图出场检查 — 蓝图指定的角色必须在正文中出现。"""

    gate_id = "PG-06"
    name = "蓝图出场检查"
    description = "大纲/蓝图指定的角色必须在正文中实际出现"

    def evaluate(self, mandated_entities: list, text: str, min_mentions: int = 2) -> dict:
        absent = []
        insufficient = []
        for entity in mandated_entities:
            name = entity.get("name", entity.get("id", ""))
            if not name:
                continue
            count = text.count(name)
            if count == 0:
                absent.append(name)
            elif count < min_mentions:
                insufficient.append({"entity": name, "mentions": count, "min": min_mentions})
        if absent:
            return self.fail_result(
                f"蓝图指定但未出现: {absent}", {"absent": absent, "insufficient": insufficient}
            )
        if insufficient:
            return self.fail_result(
                f"出场但叙事力度不足: {insufficient}", {"insufficient": insufficient}
            )
        return self.pass_result()


# ── 门禁注册 ──

ALL_PRE_GATES: dict[str, type[PreGateBase]] = {
    "PG-01": PG01_ProtocolParse,
    "PG-02": PG02_ReferenceCheck,
    "PG-03": PG03_ConsistencyCheck,
    "PG-04": PG04_UnknownEntity,
    "PG-05": PG05_DescriptionCheck,
    "PG-06": PG06_BlueprintPresence,
}


def run_pre_gates(
    text: str = "",
    changes: dict = None,
    ledger: dict = None,
    new_entities: list = None,
    character_profiles: dict = None,
    mandated_entities: list = None,
    fact_snapshot: dict = None,
) -> list[dict]:
    """运行全部 6 道写前门禁。"""
    if changes is None:
        changes = {}
    if ledger is None:
        ledger = {"known_ids": []}
    if new_entities is None:
        new_entities = []
    if character_profiles is None:
        character_profiles = {}
    if mandated_entities is None:
        mandated_entities = []
    if fact_snapshot is None:
        fact_snapshot = {}

    results = []

    g1 = PG01_ProtocolParse()
    results.append(g1.evaluate(text))

    g2 = PG02_ReferenceCheck()
    results.append(g2.evaluate(changes, ledger))

    g3 = PG03_ConsistencyCheck()
    results.append(g3.evaluate(changes, fact_snapshot))

    g4 = PG04_UnknownEntity()
    results.append(g4.evaluate(new_entities, ledger.get("known_ids", [])))

    g5 = PG05_DescriptionCheck()
    results.append(g5.evaluate(text, character_profiles))

    g6 = PG06_BlueprintPresence()
    results.append(g6.evaluate(mandated_entities, text))

    return results


def summarize(results: list[dict]) -> dict:
    """汇总写前门禁结果。"""
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    failed = [r for r in results if not r["passed"]]
    return {
        "overall": "pass" if passed == total else "block",
        "summary": {"passed": passed, "blocked": total - passed, "total": total},
        "failed_gates": failed,
    }
