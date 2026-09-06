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

# P1-7 (2026-09-07): 统一设置 HuggingFace/Transformers 离线环境变量——
# 之前散落在 README 手工步骤（"需设 HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1，
# 否则测试进入 HF 挂死"），未脚本化导致新机器跑测试可能卡在网络请求。
# 现在 conftest 在导入任何模型代码前强制离线：transformers NER 无网络时
# 快速降级正则路径，测试完全离线可复现。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


@pytest.fixture(scope="session")
def sample_ch1_text() -> str:
    """《洛阳星港》第 1 章样例文本——共享 fixture，不依赖运行中的 /chapter-1-sample 端点。

    P1-7：需要样例正文的测试应注入本 fixture，而非向 api_server 发起 HTTP 请求，
    消除测试对运行端点的隐式依赖（离线可复现、独立可测）。
    """
    from bridge.api_server import CHAPTER_1_SAMPLE

    return CHAPTER_1_SAMPLE


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
