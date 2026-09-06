"""P1-7 (2026-09-07): 测试离线环境固化 + sample 章节 fixture。

深度审计 S3 发现：测试需手动设置 HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE（README
有记录但未脚本化），否则会进入 HuggingFace 挂死；部分测试依赖运行中的
/chapter-1-sample 端点与共享样例，独立性与离线可复现性偏弱。

修复：
- tests/conftest.py 顶层 setdefault HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE /
  TOKENIZERS_PARALLELISM，任何模型代码 import 前即离线（transformers NER 无网络
  快速降级正则路径）。
- 新增 sample_ch1_text fixture：从 api_server 常量导入，供需要样例的测试注入，
  不依赖运行端点。

本测试验证两条铁律：
- conftest 已设 offline env（无需 README 手工步骤）；
- fixture 与运行端点返回一致（端点仍在 = 产品功能保留，但测试可选 fixture 注入）。

Run: python -X utf8 -m pytest tests/test_offline_env.py -v
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_conftest_sets_hf_offline_env():
    """conftest 顶层已脚本化 offline 环境变量（不依赖 README 手工步骤）。"""
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"


def test_sample_fixture_matches_endpoint(sample_ch1_text):
    """sample_ch1_text fixture 与 /chapter-1-sample 端点一致（端点保留为产品功能）。

    FastAPI 对裸 str return 做 JSON 编码（引号/换行转义），故端点需 json 解码后
    与 fixture（原始字符串）比对。
    """
    import json

    from fastapi.testclient import TestClient

    from bridge.api_server import app

    client = TestClient(app)
    resp = client.get("/chapter-1-sample")
    assert resp.status_code == 200
    assert json.loads(resp.text) == sample_ch1_text


def test_sample_fixture_is_reusable_content(sample_ch1_text):
    """fixture 提供可直接复用的样例正文（≥100字、含主角名）——测试可离线注入。"""
    assert len(sample_ch1_text) > 100
    assert "陈默" in sample_ch1_text
