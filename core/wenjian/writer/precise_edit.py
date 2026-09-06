"""精确段落改写（AnySpark 剧情链模式）。

只改目标段落，不动其余。
"""

from __future__ import annotations

import re

from wenjian.models.base import registry as model_registry


def _get_llm(api_key="", provider="anthropic", model=""):
    if api_key:
        model_name = model or {"anthropic": "claude-sonnet-4-20250514", "openai": "gpt-4o"}.get(
            provider, "claude-sonnet-4-20250514"
        )
        return model_registry.create(provider, model_name, api_key)
    raise ValueError("需要 API Key")


class ChainEditor:
    """剧情链编辑器 — 将文本拆为节点，精确修改指定节点。"""

    def split_into_nodes(self, text: str) -> list[dict]:
        """将文本拆为剧情链节点。"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        nodes = []
        for i, para in enumerate(paragraphs):
            nodes.append(
                {
                    "id": f"n{i}",
                    "type": self._detect_node_type(para),
                    "text": para,
                    "char_count": len(para),
                    "characters": self._extract_characters(para),
                }
            )
        return nodes

    def _detect_node_type(self, text: str) -> str:
        if "说" in text and ('"' in text or "「" in text or "『" in text):
            return "dialogue"
        if any(w in text for w in ["突然", "没想到", "却", "竟", "原来"]):
            return "turn"
        if any(w in text for w in ["感到", "觉得", "愤怒", "悲伤", "恐惧"]):
            return "emotion"
        if any(w in text for w in ["杀", "追", "打", "战", "攻"]):
            return "action"
        return "description"

    def _extract_characters(self, text: str) -> list[str]:
        names = re.findall(r"[「「『『](\w{2,4})[」」』』]", text)
        names += re.findall(r"(\w{2,4})(?:说|道|问|答|喊|叫)", text)
        return list(set(names))

    def edit_node(
        self,
        nodes: list[dict],
        target_id: str,
        edit_mode: str,
        instruction: str,
        api_key="",
        provider="anthropic",
        model="",
    ) -> list[dict]:
        """编辑指定节点。"""
        mc = _get_llm(api_key, provider, model)
        client = mc  # Already a provider instance

        target = None
        for n in nodes:
            if n["id"] == target_id:
                target = n
                break
        if not target:
            return nodes

        # 只替换目标节点
        prompt = f"""原文段落：\n{target["text"]}\n\n修改要求（{edit_mode}）：{instruction}\n\n只输出修改后的段落，不要输出其他内容。"""
        resp = client.chat(
            system="你是一个小说编辑。保持语气一致。",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        new_text = resp.content.strip()

        idx = None
        for i, n in enumerate(nodes):
            if n["id"] == target_id:
                idx = i
                break
        if idx is not None:
            nodes[idx]["text"] = new_text
            nodes[idx]["edited"] = True
            nodes[idx]["edit_type"] = edit_mode
            nodes[idx]["edit_instruction"] = instruction

        return nodes

    def rebuild(self, nodes: list[dict]) -> str:
        """将节点重建为完整文本。"""
        return "\n\n".join(n["text"] for n in nodes)

    def precise_edit(
        self, text: str, edit_descriptions: list[dict], api_key="", provider="anthropic", model=""
    ) -> dict:
        """批量精确编辑：[(paragraph_index_or_keyword, mode, instruction), ...]"""
        nodes = self.split_into_nodes(text)
        changes = []

        for edit in edit_descriptions:
            target = edit.get("target", "")
            mode = edit.get("mode", "tweak")
            instruction = edit.get("instruction", "")

            # 找目标节点
            target_id = None
            if isinstance(target, int) and 0 <= target < len(nodes):
                target_id = nodes[target]["id"]
            else:
                for n in nodes:
                    if target in n["text"][:50]:
                        target_id = n["id"]
                        break
            if not target_id:
                continue

            before = [n["text"] for n in nodes if n["id"] == target_id][0]
            nodes = self.edit_node(nodes, target_id, mode, instruction, api_key, provider, model)
            after = [n["text"] for n in nodes if n["id"] == target_id][0]
            if before != after:
                changes.append(
                    {"node": target_id, "mode": mode, "before": before[:100], "after": after[:100]}
                )

        return {"text": self.rebuild(nodes), "changes": changes, "nodes_edited": len(changes)}


chain_editor = ChainEditor()
