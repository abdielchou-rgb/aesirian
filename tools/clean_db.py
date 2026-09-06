"""Æsirian 数据清理工具

- clean: 删除测试残留项目（标题匹配测试模式/空项目），保留用户数据
- seed:  重建一个演示项目《洛阳星港》并提交第 1 章
用法:
  python -X utf8 tools/clean_db.py clean        # 清理测试数据
  python -X utf8 tools/clean_db.py seed         # 生成演示项目
"""
import sys
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "bridge"))

TEST_TITLE_PATTERNS = [
    r"^test", r"测试", r"probe", r"probe_", r"Blueprint", r"蓝图",
    r"上下文工程", r"Full flow", r"Belief test", r"产品化测试",
    r"persistence v", r"Mind grid probe", r"EPUB export", r"Style marketplace",
    r"深海空间站", r"火星殖民", r"e2e", r"E2E", r"质量", r"质量检测",
    r"^A detective", r"^Full flow test", r"^Test ", r"^\u03a6", r"^[A-Z][a-z]+ test",
    r"^Test premise", r"^Test story", r"^Test novel", r"premise for",
    r"^gen_", r"^ql_", r"^Blueprint", r"探测器", r"罪忆水晶探针", r"测试文本",
]

def main():
    from core.persistence.store import ProjectStore
    store = ProjectStore()
    projects = store.list_projects()
    action = sys.argv[1] if len(sys.argv) > 1 else "clean"

    if action == "clean":
        removed = 0
        kept = []
        for p in projects:
            title = p.title or ""
            is_test = any(re.search(pat, title, re.IGNORECASE) for pat in TEST_TITLE_PATTERNS)
            chapters = store.get_chapters(p.id)
            is_empty = not chapters
            if is_test or is_empty:
                store.delete_project(p.id)
                removed += 1
            else:
                kept.append(p)
        print(f"[clean] removed {removed} test/empty projects, kept {len(kept)}")
        for k in kept:
            print(f"  keep: {k.id[:10]} {k.title[:40]}")
        return

    if action == "seed":
        # 清理同名旧项目
        for p in projects:
            if "洛阳星港" in (p.title or ""):
                store.delete_project(p.id)
        import tempfile
        from bridge.nsef import NarrativeStatePackage, CharacterSeed, Tone, ConflictType
        pkg = NarrativeStatePackage(
            premise="洛阳星港上，一个修复罪忆水晶的匠人发现了军方的秘密",
            unit_text="洛阳星港上，一个修复罪忆水晶的匠人发现了军方的秘密",
            characters=[
                CharacterSeed(name="陈默", role="主角·罪忆水晶匠人"),
                CharacterSeed(name="曹渊", role="来客·安全局顾问"),
            ],
            tone=Tone.SUSPENSE,
            conflict=ConflictType.SURVIVAL,
        )
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        tmp.write(pkg.to_json())
        tmp.close()

        from core.orchestrator import Orchestrator
        orch = Orchestrator(store=store)
        project = orch.create_project_from_nsef(tmp.name)

        # 用内置示例章节作为第 1 章（api_server 的 CHAPTER_1_SAMPLE）
        from bridge.api_server import CHAPTER_1_SAMPLE
        orch.submit_chapter(project.project_id, CHAPTER_1_SAMPLE)
        print(f"[seed] demo project {project.project_id} created, "
              f"chapters={len(store.get_chapters(project.project_id))}")
        return

    print(f"unknown action: {action} (use clean|seed)")

if __name__ == "__main__":
    main()