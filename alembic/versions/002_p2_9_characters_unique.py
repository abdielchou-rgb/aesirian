"""002 — P2-9: characters (project_id, name) 唯一索引 + chapters 约束补齐。

Revision ID: 002
Revises: 001
Create Date: 2026-09-07

背景（深度审计 P2-9）：
- 001 为 characters 建的 ix_characters_project_name 是**非唯一**索引，但 store
  语义是"同名角色在同一项目内唯一"（ToM character_id=name；_persist 按 name
  反查回写）——无唯一约束时同名角色会插入多行、回写互相覆盖。
- chapters 001 已建唯一索引 ix_chapters_project_number，此处校验兜底。

升级内容：
1. 删除 characters 非唯一 ix_characters_project_name（若存在）
2. 重建为唯一索引 uq_characters_project_name（project_id, name）
3. chapters 若缺 ix_chapters_project_number 唯一索引则补建

注意：真实库 aesirian.db 的 schema 由 SQLModel create_all 生成、从未跑过 alembic
链（无 alembic_version）。对真实库请用 tools/migrate_p2_9.py（备份+幂等补索引），
不要直接在此迁移上 stamp。
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── characters: (project_id, name) 唯一 ──
    char_indexes = {i["name"] for i in inspector.get_indexes("characters")}
    # SQLite 下 ALTER 受限：唯一化通过 删旧索引→建唯一索引 实现
    if "ix_characters_project_name" in char_indexes:
        op.drop_index("ix_characters_project_name", table_name="characters")
    if "uq_characters_project_name" not in char_indexes:
        op.create_index(
            "uq_characters_project_name",
            "characters",
            ["project_id", "name"],
            unique=True,
        )

    # ── chapters: 唯一约束兜底（001 已建，此处确保存在） ──
    ch_indexes = {i["name"] for i in inspector.get_indexes("chapters")}
    if "ix_chapters_project_number" not in ch_indexes:
        op.create_index(
            "ix_chapters_project_number",
            "chapters",
            ["project_id", "number"],
            unique=True,
        )


def downgrade() -> None:
    # 回退：唯一索引降回非唯一（保守，不删 chapters 唯一约束）
    op.drop_index("uq_characters_project_name", table_name="characters")
    op.create_index("ix_characters_project_name", "characters", ["project_id", "name"])
