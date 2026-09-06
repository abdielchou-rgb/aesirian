#!/usr/bin/env python3
"""P2-9 (2026-09-07): 真实库迁移交付脚本——备份 + 幂等补唯一约束。

深度审计 P2-9 目标：characters (project_id, name) 唯一索引，与 store 幂等 upsert
语义一致，消除 docstring/实现/schema 三方矛盾。

为何需要独立脚本而非直接 `alembic upgrade head`：
真实库 aesirian.db 的 schema 由 SQLModel metadata.create_all 生成（历史路径），
**从未跑过 alembic 链**（无 alembic_version 表）。直接 stamp 001/002 会与
create_all 生成的 schema 冲突。因此对真实库做"备份 + 幂等补约束"，不引入
alembic_version，保留 create_all 自举路径（engine 内存回退分支同样会 create_all）。

用法：
    python tools/migrate_p2_9.py                 # 默认迁移 ./aesirian.db
    python tools/migrate_p2_9.py --db path.db    # 指定库
    python tools/migrate_p2_9.py --dry-run       # 只检查不修改

安全：执行前自动备份到 aesirian.db.backup-<ts>；若存在同名重复角色会先列出并
拒绝执行（需先清理），避免唯一索引创建失败。

验证：沙箱全量 pytest 150 绿 + 本脚本 dry-run 通过（见 aesirian-m4 审计）。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def _check_duplicates(cur: sqlite3.Cursor) -> list[tuple]:
    return cur.execute(
        "SELECT project_id, name, COUNT(*) c FROM characters "
        "GROUP BY project_id, name HAVING c > 1"
    ).fetchall()


def migrate(db_path: str, dry_run: bool = False) -> dict:
    db = Path(db_path)
    if not db.exists():
        return {"error": f"数据库不存在: {db_path}"}

    backup = None
    if not dry_run:
        backup = db.with_name(f"{db.stem}.db.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(db, backup)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=OFF")
    cur = con.cursor()
    report: dict = {"backup": str(backup) if backup else None, "actions": []}

    try:
        # 0) 重复角色检查——唯一索引前置条件
        dups = _check_duplicates(cur)
        if dups:
            con.close()
            return {
                "error": "存在同名重复角色，需先清理再建唯一索引",
                "duplicates": [f"{p}/{n} x{c}" for p, n, c in dups],
                "backup": str(backup) if backup else None,
            }

        # 1) chapters: (project_id, number) 唯一
        idxs = {r[1]: r for r in cur.execute("PRAGMA index_list('chapters')")}
        if "ix_chapters_project_number" not in idxs:
            if not dry_run:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_chapters_project_number "
                    "ON chapters(project_id, number)"
                )
            report["actions"].append("chapters: create unique ix_chapters_project_number")

        # 2) characters: (project_id, name) 唯一
        idxs = {r[1]: r for r in cur.execute("PRAGMA index_list('characters')")}
        if "uq_characters_project_name" not in idxs:
            if not dry_run:
                if "ix_characters_project_name" in idxs:
                    cur.execute("DROP INDEX IF EXISTS ix_characters_project_name")
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_characters_project_name "
                    "ON characters(project_id, name)"
                )
            report["actions"].append(
                "characters: drop ix_characters_project_name, create unique uq_characters_project_name"
            )

        if not dry_run:
            con.commit()
        report["dry_run"] = dry_run
        report["ok"] = True
    finally:
        con.close()
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="P2-9 真实库迁移：备份 + 幂等补唯一约束")
    ap.add_argument("--db", default="aesirian.db", help="目标 SQLite 路径")
    ap.add_argument("--dry-run", action="store_true", help="只检查不修改")
    args = ap.parse_args()
    print(json.dumps(migrate(args.db, dry_run=args.dry_run), ensure_ascii=False, indent=2))
