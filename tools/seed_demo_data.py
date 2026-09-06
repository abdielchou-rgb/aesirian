"""M3-2 演示种子数据工具。

作用：
1. 读取《洛阳星港》第 1 章（优先默认 DB b541e7835c57，否则 fallback examples/luoyang/ch1.txt）；
2. forward_derive 生成 FourCardProject（2 角色锚 + framework + chapters + sample）；
3. 执行一次代表性编辑（改主角 want），取前 3 条跨卡联动 diff 作为「提案制」样例；
4. 输出 pwa/demo/demo_luoyang_project.json（four_cards.html「加载演示」按钮读取）；
5. 将角色 beliefs/goals 种子写入默认 DB（aesirian.db），补齐演示项目空 beliefs/goals 数据洞。

用法: python tools/seed_demo_data.py [--force]
说明:
  - demo JSON (pwa/demo/demo_luoyang_project.json) 是 curated 演示资产（多角色、hand-maintained，
    见 core/diff_engine.py _drop_shell_biographies 注释）。默认若已存在则跳过不覆盖；
    --force 时用当前 ch1 重新生成（forward_derive：有 LLM key 走高质路径，否则规则降级）。
  - DB 不存在时自动跳过 DB beliefs/goals 种子（fresh clone 场景）。
只生成种子数据与演示 JSON，不修改 diff_engine / four_cards 引擎逻辑。
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from core.diff_engine import forward_derive, propose_diff, CardEdit
from core.four_cards import FourCardProject

DEMO_PROJECT_ID = "b541e7835c57"
OUT_JSON = os.path.join(ROOT, "pwa", "demo", "demo_luoyang_project.json")
FALLBACK_CH1 = os.path.join(ROOT, "examples", "luoyang", "ch1.txt")
DB_PATH = os.path.join(ROOT, "aesirian.db")


def load_chapter1() -> str:
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        row = con.execute(
            "SELECT text FROM chapters WHERE project_id=? AND number=1 ORDER BY id LIMIT 1",
            (DEMO_PROJECT_ID,),
        ).fetchone()
        con.close()
        if row and row[0].strip():
            print(f"ch1 from DB: {len(row[0].strip())} chars")
            return row[0].strip()
    except Exception as e:
        print("DB read failed:", e)
    text = open(FALLBACK_CH1, encoding="utf-8").read().strip()
    print(f"ch1 from fallback file: {len(text)} chars")
    return text


def build_demo_project(ch1: str) -> FourCardProject:
    p = forward_derive(ch1)
    if not isinstance(p, FourCardProject):
        p = FourCardProject.model_validate(p)
    print("derived:", [b.name for b in p.biographies], "| framework:", len(p.framework),
          "| chapters:", len(p.chapters))
    # 代表性编辑：给主角 want 加代价措辞，触发跨卡联动
    bio = p.biographies[0]
    edit = CardEdit(
        card="biographies", index=0, field="want",
        before=bio.want, after=f"{bio.want}，哪怕赌上整条命",
    )
    diffs = propose_diff(edit, p)
    kept = diffs[:3]
    p.pending_diffs = list(kept)
    for d in kept:
        print(f"  sample diff -> {d.target_card}.{d.field}: {d.rationale[:50]}")
    return p


def seed_db_beliefs_goals(ch1: str) -> dict:
    """将 demo 项目角色 beliefs/goals 写入默认 DB（不覆盖已有非空值）。"""
    result = {}
    if not os.path.exists(DB_PATH):
        print("skip DB seed: aesirian.db not found")
        return result
    import sqlite3
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            "SELECT id,name,beliefs_json,goals_json FROM characters WHERE project_id=?",
            (DEMO_PROJECT_ID,),
        ).fetchall()
        seeds = {
            "陈默": {
                "beliefs": {
                    "军用级记忆还原的案子会再次引来灾祸": {
                        "value": True, "confidence": 0.95,
                        "source": "目击", "is_erroneous": True,
                        "updated_at": 0,
                    },
                    "守住'不碰军用的'底线就能让过去的灾祸不再发生": {
                        "value": True, "confidence": 0.9,
                        "source": "目击", "is_erroneous": True,
                        "updated_at": 0,
                    },
                    "罪忆水晶里藏着军方不可告人的秘密": {
                        "value": True, "confidence": 0.75,
                        "source": "目击", "is_erroneous": False,
                        "updated_at": 0,
                    },
                },
                "goals": [
                    {"description": "拒绝重蹈覆辙，不再接军用级记忆还原的案子",
                     "priority": 1, "active": True, "since_chapter": 1},
                    {"description": "在曹渊的反复施压下守住'不碰军用'的底线",
                     "priority": 2, "active": True, "since_chapter": 1},
                ],
            },
            "曹渊": {
                "beliefs": {
                    "失乐园协议继续推进会伤害女儿": {
                        "value": True, "confidence": 0.9,
                        "source": "推测", "is_erroneous": False,
                        "updated_at": 0,
                    },
                    "陈默是唯一能还原A-7罪忆水晶的匠人": {
                        "value": True, "confidence": 0.85,
                        "source": "目击", "is_erroneous": False,
                        "updated_at": 0,
                    },
                    "只有把水晶里的秘密公之于众才能阻止协议": {
                        "value": True, "confidence": 0.6,
                        "source": "推测", "is_erroneous": False,
                        "updated_at": 0,
                    },
                },
                "goals": [
                    {"description": "让陈默还原军用水晶里的记忆并复制出来",
                     "priority": 1, "active": True, "since_chapter": 1},
                    {"description": "阻止失乐园协议继续伤害女儿",
                     "priority": 2, "active": True, "since_chapter": 1},
                ],
            },
        }
        for cid, name, beliefs_json, goals_json in rows:
            if name not in seeds:
                continue
            old_b = json.loads(beliefs_json) if beliefs_json else {}
            old_g = json.loads(goals_json) if goals_json else []
            new_b = {**seeds[name]["beliefs"], **old_b}
            new_g = seeds[name]["goals"] + [g for g in old_g if g.get("description") not in
                                            {x["description"] for x in seeds[name]["goals"]}]
            con.execute(
                "UPDATE characters SET beliefs_json=?, goals_json=? WHERE id=?",
                (json.dumps(new_b, ensure_ascii=False),
                 json.dumps(new_g, ensure_ascii=False), cid),
            )
            result[name] = (len(new_b), len(new_g))
        con.commit()
    finally:
        con.close()
    return result


def main() -> None:
    ch1 = load_chapter1()
    if os.path.exists(OUT_JSON) and "--force" not in sys.argv:
        print("demo json 已存在，保留 curated 演示资产:", OUT_JSON)
        print("提示: 用当前 ch1 重新生成 -> python tools/seed_demo_data.py --force")
    else:
        p = build_demo_project(ch1)
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(p.model_dump(), f, ensure_ascii=False, indent=1)
        print("demo json written:", OUT_JSON)
    seeded = seed_db_beliefs_goals(ch1)
    print("db seeded:", seeded)


if __name__ == "__main__":
    main()
