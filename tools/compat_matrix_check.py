"""M1-2 matrix gate: assert the 7 sandbox fixes from roundtable-20260905 Appendix A.

Reused by CI (.github/workflows/ci.yml) and by every tox matrix env (tox.ini).

Pure text-level assertions; no third-party imports; runs on Python 3.10+.
Each failed assertion means one of the 7 fixes has regressed and must be
re-fixed before the compatibility matrix can go green.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "core"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_failures() -> list[str]:
    failures: list[str] = []

    # F1/F2 (fix 1 & 2): datetime.UTC x3 -> timezone.utc (py3.10 compatibility)
    for path in sorted(CORE.rglob("*.py")):
        text = _read(path)
        if "datetime.UTC" in text:
            failures.append(f"py3.10-incompatible datetime.UTC remains in {path}")

    # F1 store.py details: timezone.utc + QueuePool/StaticPool import + in-memory shared engine
    store_path = CORE / "persistence" / "store.py"
    store = _read(store_path)
    store_tokens = (
        "timezone.utc",
        "QueuePool",
        "StaticPool",
        "_build_engine",
        "_memory_engine",
        "create_all",
    )
    missing = [token for token in store_tokens if token not in store]
    if missing:
        failures.append(f"{store_path} is missing expected tokens: {', '.join(missing)}")

    # F2 outline.py uses timezone.utc
    outline_path = CORE / "planning" / "outline.py"
    if "timezone.utc" not in _read(outline_path):
        failures.append(f"{outline_path} does not use timezone.utc")

    # F4 pydantic-ai renames: OpenAIChatModel alias + models.gemini -> models.google
    pai_path = CORE / "pydantic_ai_engine.py"
    pai = _read(pai_path)
    pai_tokens = ("OpenAIChatModel", "pydantic_ai.models.google")
    missing_pai = [token for token in pai_tokens if token not in pai]
    if missing_pai:
        failures.append(f"{pai_path} is missing expected tokens: {', '.join(missing_pai)}")
    if "pydantic_ai.models.gemini" in pai:
        failures.append(f"{pai_path} still imports the removed models.gemini path")

    # F5 llm_used NameError fix in orchestrator
    orch_path = CORE / "orchestrator.py"
    if "llm_used = False" not in _read(orch_path):
        failures.append(f"{orch_path} lost the llm_used initialization (NameError fix)")

    # F6 test_e2e.py asserts shared in-memory engine across ProjectStore instances
    e2e_path = ROOT / "tests" / "test_e2e.py"
    e2e = _read(e2e_path)
    if "ProjectStore()" not in e2e:
        failures.append(f"{e2e_path} lost the shared-engine reload assertion")

    # F7 test_core.py covers BeliefSource.INFERENCE role conflict
    tcore_path = ROOT / "tests" / "test_core.py"
    if "BeliefSource.INFERENCE" not in _read(tcore_path):
        failures.append(f"{tcore_path} lost the BeliefSource.INFERENCE assertion")

    return failures


def main() -> int:
    failures = _collect_failures()
    if failures:
        sys.stdout.write("compat_matrix_check FAILED:\n")
        for item in failures:
            sys.stdout.write(f"  - {item}\n")
        return 1
    sys.stdout.write(
        "compat_matrix_check OK: 7 sandbox fixes (roundtable-20260905 Appendix A) are present.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
