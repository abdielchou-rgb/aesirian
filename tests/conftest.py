"""
测试隔离 fixture（O1）：所有 pytest 用例共享一个临时 SQLite DB，
通过环境变量 AESIRIAN_DB_URL 注入 ProjectStore 默认路径（见
core/persistence/store.py），避免测试污染主库 aesirian.db。

注意：fixture 为 session 级 autouse，先于所有测试执行，确保任何
ProjectStore() 实例化都命中临时库；file-backed 临时库按模型元数据
自建 schema（主库 schema 由 Alembic 管理，测试库无需迁移）。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_test_db(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("aesirian_tests") / "test.db"
    os.environ["AESIRIAN_DB_URL"] = f"sqlite:///{db_file.as_posix()}"

    # 先实例化一次 ProjectStore（此时已命中临时库），按模型建表
    from sqlmodel import SQLModel
    from core.persistence.store import ProjectStore

    store = ProjectStore()
    SQLModel.metadata.create_all(store.engine)

    yield db_file

    os.environ.pop("AESIRIAN_DB_URL", None)
