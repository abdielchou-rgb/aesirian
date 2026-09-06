"""
Æsirian 插件系统（#23 轻量版）

规范：plugins/ 目录下每个子目录一个 aesirian-plugin.json + Python 模块。
支持的插件类型：
  - gate     : check(text, context) -> {level, message}
  - analyzer : analyze(text) -> dict[str, float]

加载器：启动时扫描 plugins/，验证 spec，注册到 PLUGINS 注册表。
API 端点在 bridge/api_server.py 中暴露 /plugins。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # core/plugins/ -> core/ -> 项目根
PLUGINS_DIR = os.path.join(ROOT, "plugins")

VALID_TYPES = {"gate", "analyzer"}
VALID_LEVELS = {"PASS", "WARN", "BLOCK"}


@dataclass
class PluginSpec:
    name: str
    version: str
    type: str
    entry_point: str  # "module:ClassName" 或 "module:function"
    description: str = ""
    permissions: list = field(default_factory=list)
    dir_path: str = ""


@dataclass
class LoadedPlugin:
    spec: PluginSpec
    instance: object


PLUGINS: dict[str, LoadedPlugin] = {}
_load_errors: list[str] = []


def _load_spec(dir_path: str) -> PluginSpec | None:
    spec_path = os.path.join(dir_path, "aesirian-plugin.json")
    if not os.path.isfile(spec_path):
        return None
    try:
        with open(spec_path, encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("type") not in VALID_TYPES:
            _load_errors.append(f"{dir_path}: unknown type {raw.get('type')}")
            return None
        if not raw.get("name") or not raw.get("entry_point"):
            _load_errors.append(f"{dir_path}: missing name/entry_point")
            return None
        return PluginSpec(
            name=raw["name"],
            version=raw.get("version", "0.0.0"),
            type=raw["type"],
            entry_point=raw["entry_point"],
            description=raw.get("description", ""),
            permissions=raw.get("permissions", []),
            dir_path=dir_path,
        )
    except (json.JSONDecodeError, KeyError) as e:
        _load_errors.append(f"{dir_path}: bad spec — {e}")
        return None


def _load_plugin(spec: PluginSpec) -> object | None:
    module_name, _, target = spec.entry_point.partition(":")
    py_path = os.path.join(spec.dir_path, module_name + ".py")
    if not os.path.isfile(py_path):
        _load_errors.append(f"{spec.name}: module file missing — {py_path}")
        return None
    try:
        mod_id = f"aesirian_plugin_{spec.name.replace('-', '_')}"
        mod_spec = importlib.util.spec_from_file_location(mod_id, py_path)
        module = importlib.util.module_from_spec(mod_spec)
        sys.modules[mod_id] = module
        mod_spec.loader.exec_module(module)

        if target:  # class 实例化
            cls = getattr(module, target, None)
            if cls is None:
                _load_errors.append(f"{spec.name}: class {target} not found")
                return None
            return cls()
    except Exception as e:
        _load_errors.append(f"{spec.name}: load failed — {e}")
        return None
    else:
        return module  # 函数式插件：直接用模块级函数


def load_plugins() -> int:
    """扫描 plugins/ 并加载。返回加载数。"""
    PLUGINS.clear()
    _load_errors.clear()
    if not os.path.isdir(PLUGINS_DIR):
        return 0
    for entry in sorted(os.listdir(PLUGINS_DIR)):
        dir_path = os.path.join(PLUGINS_DIR, entry)
        if not os.path.isdir(dir_path) or entry.startswith(("_", ".")):
            continue
        spec = _load_spec(dir_path)
        if not spec:
            continue
        instance = _load_plugin(spec)
        if instance is not None:
            PLUGINS[spec.name] = LoadedPlugin(spec=spec, instance=instance)
    return len(PLUGINS)


def run_gate_plugins(text: str, context: dict | None = None) -> list[dict]:
    """运行所有 gate 类插件，返回标准化结果"""
    results = []
    context = context or {}
    for name, p in PLUGINS.items():
        if p.spec.type != "gate":
            continue
        try:
            r = p.instance.check(text, context)
            level = r.get("level", "PASS")
            if level not in VALID_LEVELS:
                level = "WARN"
            results.append(
                {
                    "gate_id": f"PLUGIN::{name}",
                    "gate_name": p.spec.description or name,
                    "level": level,
                    "message": str(r.get("message", ""))[:200],
                    "suggestion": str(r.get("suggestion", ""))[:120],
                    "plugin": name,
                }
            )
        except Exception as e:
            results.append(
                {
                    "gate_id": f"PLUGIN::{name}",
                    "gate_name": f"插件 {name} 执行出错",
                    "level": "WARN",
                    "message": str(e)[:150],
                    "plugin": name,
                }
            )
    return results


def run_analyzer_plugins(text: str) -> dict[str, float]:
    """运行所有 analyzer 类插件，返回维度名 -> 值"""
    dims: dict[str, float] = {}
    for name, p in PLUGINS.items():
        if p.spec.type != "analyzer":
            continue
        try:
            r = p.instance.analyze(text)
            if isinstance(r, dict):
                for k, v in r.items():
                    if isinstance(v, (int, float)):
                        dims[f"plugin:{name}:{k}"] = round(float(v), 4)
        except Exception:
            continue
    return dims


def list_plugins() -> list[dict]:
    return [
        {
            "name": p.spec.name,
            "version": p.spec.version,
            "type": p.spec.type,
            "description": p.spec.description,
            "permissions": p.spec.permissions,
        }
        for p in PLUGINS.values()
    ]


def load_errors() -> list[str]:
    return list(_load_errors)


# 启动即加载（惰性幂等——重复调用只重扫）
load_plugins()
