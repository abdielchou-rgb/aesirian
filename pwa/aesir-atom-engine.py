#!/usr/bin/env python3
"""Æsir 原子兼容性矩阵 + 探索-利用平衡引擎

两个核心机制：
  1. 情境组合规则：定义原子之间的兼容/冲突关系，防止发散时产生自相矛盾的组合
  2. 探索-利用平衡：在用户风格档案中引入"离群度"参数，确保系统不会完全收敛

用法:
  python3 aesir-atom-engine.py --check protagonist=探索者 tone=冷峻写实 conflict=关系冲突
  python3 aesir-atom-engine.py --diverge "一个关于错过的故事" --profile '{"tones":{"冷峻写实":3}}'
  python3 aesir-atom-engine.py --server --port 8767
"""

import json, math, random, sys
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════
#  1. 原子兼容性矩阵
# ═══════════════════════════════════════════════════════════════

# 兼容性等级
COMPATIBLE = 2      # 兼容：可以同时出现
NEUTRAL = 1         # 中性：不冲突也不协同
WEAK_CONFLICT = 0   # 弱冲突：尽量避免
STRONG_CONFLICT = -1 # 强冲突：不应同时出现

# 原子兼容性矩阵（仅定义冲突对，未列出 = 中性）
# 格式：{ (类别A, 原子A, 类别B, 原子B): 兼容性等级 }
ATOM_CONFLICTS = {
    # ── 调性之间的强冲突 ──
    ("tone", "温暖治愈", "tone", "激烈狂暴"): STRONG_CONFLICT,
    ("tone", "温暖治愈", "tone", "黑色幽默"): WEAK_CONFLICT,
    ("tone", "温暖治愈", "tone", "悬疑暗流"): NEUTRAL,
    ("tone", "温暖治愈", "tone", "诗意思辨"): COMPATIBLE,
    ("tone", "冷峻写实", "tone", "温暖治愈"): WEAK_CONFLICT,
    ("tone", "冷峻写实", "tone", "诗意思辨"): COMPATIBLE,
    ("tone", "黑色幽默", "tone", "诗意思辨"): WEAK_CONFLICT,
    ("tone", "悬疑暗流", "tone", "温暖治愈"): NEUTRAL,
    ("tone", "悬疑暗流", "tone", "激烈狂暴"): COMPATIBLE,
    # ── 调性与设定之间的兼容规则 ──
    ("tone", "温暖治愈", "setting", "失落世界"): WEAK_CONFLICT,
    ("tone", "温暖治愈", "setting", "封闭空间"): NEUTRAL,
    ("tone", "冷峻写实", "setting", "小社会"): COMPATIBLE,
    ("tone", "冷峻写实", "setting", "旅途"): COMPATIBLE,
    ("tone", "悬疑暗流", "setting", "失落世界"): COMPATIBLE,
    ("tone", "悬疑暗流", "setting", "封闭空间"): COMPATIBLE,
    ("tone", "激烈狂暴", "setting", "日常入侵"): COMPATIBLE,
    ("tone", "诗意思辨", "setting", "旅途"): COMPATIBLE,
    # ── 冲突类型与主角类型的匹配 ──
    ("conflict", "身份冲突", "protagonist", "天选之人"): COMPATIBLE,
    ("conflict", "身份冲突", "protagonist", "局外人"): COMPATIBLE,
    ("conflict", "身份冲突", "protagonist", "普通人"): WEAK_CONFLICT,
    ("conflict", "生存冲突", "protagonist", "普通人"): COMPATIBLE,
    ("conflict", "生存冲突", "protagonist", "复仇者"): COMPATIBLE,
    ("conflict", "生存冲突", "protagonist", "天选之人"): WEAK_CONFLICT,
    ("conflict", "价值观冲突", "protagonist", "探索者"): COMPATIBLE,
    ("conflict", "价值观冲突", "protagonist", "天选之人"): NEUTRAL,
    ("conflict", "关系冲突", "protagonist", "守护者"): COMPATIBLE,
    ("conflict", "关系冲突", "protagonist", "复仇者"): WEAK_CONFLICT,
    ("conflict", "资源冲突", "protagonist", "守护者"): WEAK_CONFLICT,
    ("conflict", "认知冲突", "protagonist", "探索者"): COMPATIBLE,
    ("conflict", "认知冲突", "protagonist", "局外人"): COMPATIBLE,
    # ── 转折与冲突的搭配 ──
    ("turn", "角色反转", "conflict", "关系冲突"): COMPATIBLE,
    ("turn", "角色反转", "conflict", "价值观冲突"): COMPATIBLE,
    ("turn", "秘密揭露", "conflict", "认知冲突"): COMPATIBLE,
    ("turn", "秘密揭露", "conflict", "身份冲突"): COMPATIBLE,
    ("turn", "代价显现", "conflict", "生存冲突"): COMPATIBLE,
    ("turn", "外力介入", "conflict", "资源冲突"): COMPATIBLE,
}

# 协同规则：某些原子组合在一起会产生更好的效果
ATOM_SYNERGIES = [
    (("tone", "悬疑暗流"), ("turn", "秘密揭露"), 1.3),
    (("tone", "温暖治愈"), ("turn", "代价显现"), 1.2),
    (("tone", "冷峻写实"), ("conflict", "生存冲突"), 1.3),
    (("tone", "诗意思辨"), ("protagonist", "探索者"), 1.2),
    (("tone", "激烈狂暴"), ("turn", "角色反转"), 1.3),
    (("setting", "封闭空间"), ("conflict", "生存冲突"), 1.3),
    (("setting", "旅途"), ("turn", "外力介入"), 1.2),
    (("protagonist", "局外人"), ("conflict", "身份冲突"), 1.4),
    (("protagonist", "复仇者"), ("turn", "角色反转"), 1.3),
    (("protagonist", "守护者"), ("conflict", "关系冲突"), 1.3),
]


def check_compatibility(atom_combo: dict) -> dict:
    """检查一组原子组合是否自洽

    输入示例：{"tone": "冷峻写实", "protagonist": "复仇者", "conflict": "生存冲突"}
    输出示例：{"score": 0.85, "conflicts": [], "synergies": [...], "suggestion": ""}
    """
    conflicts = []
    synergies = []
    conflict_score = 0
    synergy_score = 0

    # 检查所有配对
    pairs = []
    categories = list(atom_combo.keys())
    for i in range(len(categories)):
        for j in range(i+1, len(categories)):
            cat_a = categories[i]
            atom_a = atom_combo[cat_a]
            cat_b = categories[j]
            atom_b = atom_combo[cat_b]

            # 查冲突表
            key = (cat_a, atom_a, cat_b, atom_b)
            key_rev = (cat_b, atom_b, cat_a, atom_a)
            compat = ATOM_CONFLICTS.get(key) or ATOM_CONFLICTS.get(key_rev)

            if compat == STRONG_CONFLICT:
                conflicts.append(f"「{atom_a}」×「{atom_b}」强冲突")
                conflict_score -= 2
            elif compat == WEAK_CONFLICT:
                conflicts.append(f"「{atom_a}」×「{atom_b}」弱冲突")
                conflict_score -= 1
            elif compat == COMPATIBLE:
                synergies.append(f"「{atom_a}」+「{atom_b}」兼容")
                synergy_score += 1

    # 查协同规则
    for (cat_a, atom_a), (cat_b, atom_b), multiplier in ATOM_SYNERGIES:
        if cat_a in categories and atom_combo.get(cat_a) == atom_a:
            if cat_b in categories and atom_combo.get(cat_b) == atom_b:
                synergies.append(f"「{atom_a}」×「{atom_b}」协同 ×{multiplier}")
                synergy_score += multiplier

    # 综合评分（0-1 之间）
    raw_score = 0.7 + (synergy_score / 10) + (conflict_score / 10)
    final_score = max(0.1, min(1.0, raw_score))

    # 建议
    suggestion = ""
    if conflict_score < -2:
        suggestion = "这组原子存在较多冲突，建议替换冲突最严重的原子"
    elif conflict_score < 0:
        suggestion = "有轻微冲突，可以考虑调整其中一个原子以获得更自洽的组合"
    elif synergy_score > 2:
        suggestion = "这组原子搭配协同效应很好"
    elif synergy_score > 0:
        suggestion = "组合基本自洽，没有明显冲突"

    return {
        "score": round(final_score, 2),
        "conflicts": conflicts,
        "synergies": synergies,
        "conflict_level": "strong" if conflict_score < -2 else "weak" if conflict_score < 0 else "none",
        "suggestion": suggestion,
    }


def repair_combo(atom_combo: dict) -> dict:
    """修复原子组合：用兼容性更好的原子替换冲突原子

    返回：修复后的组合 + 变更说明
    """
    result = dict(atom_combo)
    check = check_compatibility(result)
    changes = []

    # 如果有强冲突/多弱冲突，尝试替换
    if check["conflict_level"] in ("strong", "weak") and check["conflicts"]:
        # 找到冲突最严重的类别，替换该类别的原子
        # 从预定义的原子池中选择兼容性最好的替代
        from aesir_narrative_intel import ATOM_TYPE_MAP

        for conflict_desc in check["conflicts"]:
            # 提取冲突中涉及的原子名
            for cat in ["tone", "protagonist", "conflict", "setting", "turn"]:
                if cat not in result:
                    continue
                current = result[cat]
                # 如果当前原子出现在冲突描述中
                if f"「{current}」" in conflict_desc:
                    # 从同类别中选择一个不会产生冲突的替代
                    candidates = ATOM_TYPE_MAP.get(cat, {}).keys()
                    best = None
                    best_score = -999
                    for candidate in candidates:
                        if candidate == current:
                            continue
                        test_combo = dict(result)
                        test_combo[cat] = candidate
                        test_check = check_compatibility(test_combo)
                        if test_check["score"] > best_score and test_check["conflict_level"] == "none":
                            best_score = test_check["score"]
                            best = candidate
                    if best and best_score > check["score"]:
                        changes.append(f"{cat}: {current} → {best}")
                        result[cat] = best
                        break  # 一次只改一个

    return {
        "original": atom_combo,
        "repaired": result,
        "changes": changes,
        "original_score": check["score"],
        "repaired_score": check_compatibility(result)["score"] if changes else check["score"],
    }


# ═══════════════════════════════════════════════════════════════
#  2. 探索-利用平衡引擎
# ═══════════════════════════════════════════════════════════════

def diverge_balanced(
    idea: str,
    style_profile: dict = None,
    explore_ratio: float = 0.2,
    total_worldlines: int = 5,
) -> dict:
    """基于探索-利用平衡生成世界线配置

    - explore_ratio=0 时全利用（完全从用户偏好中选择）
    - explore_ratio=1 时全探索（完全随机）
    - 默认 0.2：5 条中 4 条利用 + 1 条探索

    返回：每条世界线的原子组合 + 属性（利用/探索）
    """
    profile = style_profile or {}
    tones = list(ATOM_CONFLICTS.keys())  # 简化：实际应从原子库获取

    # 原子库（简化版）
    atom_pool = {
        "tone": ["冷峻写实", "温暖治愈", "黑色幽默", "悬疑暗流", "诗意思辨", "激烈狂暴"],
        "protagonist": ["普通人", "天选之人", "局外人", "复仇者", "守护者", "探索者"],
        "conflict": ["身份冲突", "资源冲突", "价值观冲突", "关系冲突", "生存冲突", "认知冲突"],
        "setting": ["封闭空间", "双界穿梭", "旅途", "小社会", "日常入侵", "失落世界"],
        "turn": ["秘密揭露", "角色反转", "假胜利", "外力介入", "代价显现", "认知升级"],
    }

    # 从风格档案中提取偏好
    preferred_tone = ""
    preferred_conflict = ""
    if profile:
        tones_pref = profile.get("tones", {})
        conflicts_pref = profile.get("conflicts", {})
        if tones_pref:
            preferred_tone = max(tones_pref, key=tones_pref.get)
        if conflicts_pref:
            preferred_conflict = max(conflicts_pref, key=conflicts_pref.get)

    worldlines = []
    explore_count = max(1, round(total_worldlines * explore_ratio))
    exploit_count = total_worldlines - explore_count

    # 生成利用型世界线
    for i in range(exploit_count):
        combo = {}
        # 调性：优先选择用户的偏好调性，但加一点偏移避免重复
        if preferred_tone:
            tone_idx = atom_pool["tone"].index(preferred_tone) if preferred_tone in atom_pool["tone"] else 0
            combo["tone"] = atom_pool["tone"][(tone_idx + i) % len(atom_pool["tone"])]
        else:
            combo["tone"] = random.choice(atom_pool["tone"])

        # 冲突：类似逻辑
        if preferred_conflict:
            conf_idx = atom_pool["conflict"].index(preferred_conflict) if preferred_conflict in atom_pool["conflict"] else 0
            combo["conflict"] = atom_pool["conflict"][(conf_idx + i * 2) % len(atom_pool["conflict"])]
        else:
            combo["conflict"] = random.choice(atom_pool["conflict"])

        # 主角和设定：从偏好关联的高兼容选项中选
        for cat in ["protagonist", "setting", "turn"]:
            candidates = atom_pool[cat]
            # 选择与已选项兼容性最好的
            best = None
            best_score = -999
            for c in candidates:
                test = dict(combo)
                test[cat] = c
                ck = check_compatibility(test)
                if ck["score"] > best_score:
                    best_score = ck["score"]
                    best = c
            combo[cat] = best or random.choice(candidates)

        worldlines.append({
            "id": len(worldlines) + 1,
            "atoms": combo,
            "type": "exploit",
            "compatibility": check_compatibility(combo),
        })

    # 生成探索型世界线（故意偏离用户偏好）
    for i in range(explore_count):
        combo = {}
        # 故意选择与用户偏好相反的调性
        if preferred_tone:
            # 找距离最远的调性（从兼容性矩阵中找强冲突的）
            opposite_tones = []
            for t in atom_pool["tone"]:
                if t == preferred_tone:
                    continue
                compat = ATOM_CONFLICTS.get(("tone", preferred_tone, "tone", t))
                if compat == STRONG_CONFLICT or compat == WEAK_CONFLICT:
                    opposite_tones.append(t)
            combo["tone"] = random.choice(opposite_tones) if opposite_tones else random.choice([t for t in atom_pool["tone"] if t != preferred_tone])
        else:
            combo["tone"] = random.choice(atom_pool["tone"])

        # 冲突也选择非偏好
        if preferred_conflict:
            combo["conflict"] = random.choice([c for c in atom_pool["conflict"] if c != preferred_conflict])
        else:
            combo["conflict"] = random.choice(atom_pool["conflict"])

        # 其余原子尽量不重合
        for cat in ["protagonist", "setting", "turn"]:
            # 避开其他世界线中已经选过的
            used = set()
            for wl in worldlines:
                if cat in wl.get("atoms", {}):
                    used.add(wl["atoms"][cat])
            candidates = [c for c in atom_pool[cat] if c not in used]
            if not candidates:
                candidates = atom_pool[cat]
            combo[cat] = random.choice(candidates)

        worldlines.append({
            "id": len(worldlines) + 1,
            "atoms": combo,
            "type": "explore",
            "compatibility": check_compatibility(combo),
        })

    # 按 id 排序（让探索型分散在列表中，不集中在一端）
    random.shuffle(worldlines)
    for i, wl in enumerate(worldlines):
        wl["id"] = i + 1

    return {
        "total": total_worldlines,
        "exploit_count": exploit_count,
        "explore_count": explore_count,
        "explore_ratio": explore_ratio,
        "worldlines": worldlines,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI / API
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Æsir 原子引擎")
    parser.add_argument('--check', nargs='+', help='检查原子组合：protagonist=探索者 tone=冷峻写实')
    parser.add_argument('--diverge', help='基于探索-利用平衡方式发散（用 --profile 传入偏好）')
    parser.add_argument('--profile', default='{}', help='风格档案 JSON')
    parser.add_argument('--explore-ratio', type=float, default=0.2, help='探索比例 0-1')
    parser.add_argument('--server', '-s', action='store_true', help='启动 API 服务')
    parser.add_argument('--port', type=int, default=8767, help='API 端口')
    args = parser.parse_args()

    if args.check:
        combo = {}
        for item in args.check:
            if '=' in item:
                k, v = item.split('=', 1)
                combo[k] = v
        if not combo:
            print("请提供原子组合，如 --check tone=冷峻写实 protagonist=复仇者")
            sys.exit(1)
        result = check_compatibility(combo)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # 如果有冲突，自动修复
        if result["conflict_level"] in ("strong", "weak"):
            repair = repair_combo(combo)
            print("\n⟡ 自动修复建议:")
            print(json.dumps(repair, ensure_ascii=False, indent=2))

    elif args.diverge:
        idea = args.diverge
        try:
            profile = json.loads(args.profile)
        except:
            profile = {}
        result = diverge_balanced(idea, profile, args.explore_ratio)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.server:
        run_server(args.port)

    else:
        # 交互模式
        print("✦ Æsir 原子引擎")
        print("1. 检查原子兼容性")
        print("2. 探索-利用平衡发散")
        choice = input("选择 (1/2): ").strip()
        if choice == "1":
            combo = {}
            for cat in ["tone", "protagonist", "conflict", "setting", "turn"]:
                val = input(f"  {cat} (留空跳过): ").strip()
                if val:
                    combo[cat] = val
            if combo:
                result = check_compatibility(combo)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif choice == "2":
            idea = input("模糊想法: ").strip()
            result = diverge_balanced(idea)
            for wl in result["worldlines"]:
                label = "✦ 尝试方向" if wl["type"] == "explore" else "  "
                print(f"  {label} 世界线 {wl['id']}: {wl['atoms']}")


def run_server(port=8767):
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
    except ImportError:
        print("需要 Python 标准库 http.server")
        sys.exit(1)

    class AtomEngineHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)

                if path == '/check':
                    combo = data.get("atoms", {})
                    if not combo:
                        self._json(400, {"error": "atoms 不能为空"})
                        return
                    result = check_compatibility(combo)
                    if result["conflict_level"] in ("strong", "weak") and data.get("repair", True):
                        result["repair"] = repair_combo(combo)
                    self._json(200, result)

                elif path == '/diverge':
                    idea = data.get("idea", "")
                    profile = data.get("style_profile", {})
                    explore_ratio = data.get("explore_ratio", 0.2)
                    if not idea:
                        self._json(400, {"error": "idea 不能为空"})
                        return
                    result = diverge_balanced(idea, profile, explore_ratio)
                    self._json(200, result)

                elif path == '/health':
                    self._json(200, {"status": "ok", "conflict_rules": len(ATOM_CONFLICTS), "synergies": len(ATOM_SYNERGIES)})
                else:
                    self._json(404, {"error": "not_found"})
            except Exception as e:
                self._json(500, {"error": str(e)})

        def do_OPTIONS(self):
            self.send_response(200)
            self._cors_headers()
            self.end_headers()

        def _cors_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')

        def _json(self, code, data):
            self.send_response(code)
            self._cors_headers()
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

        def log_message(self, format, *args):
            print(f"  [{self.address_string()}] {format % args}", file=sys.stderr)

    server = HTTPServer(('0.0.0.0', port), AtomEngineHandler)
    print(f"✦ Æsir 原子引擎 API 运行在 http://localhost:{port}")
    print(f"  POST /check   — 检查原子组合兼容性")
    print(f"  POST /diverge — 探索-利用平衡发散")
    print(f"  GET  /health  — 健康检查")
    print(f"  冲突规则: {len(ATOM_CONFLICTS)} 条 / 协同规则: {len(ATOM_SYNERGIES)} 条")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n关闭服务器")
        server.server_close()


if __name__ == "__main__":
    main()
