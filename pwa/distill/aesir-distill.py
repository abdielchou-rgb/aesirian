#!/usr/bin/env python3
"""Æsir 蒸馏管道 — 从文本中提取叙事原子和风格特征

用法:
  python3 aesir-distill.py --file novel.txt
  python3 aesir-distill.py --text "很久很久以前..."
  python3 aesir-distill.py --server   # 启动 API 服务

输出: 风格特征 JSON，可直接注入 Æsir 发散引擎
"""

import json, re, math, sys, os
from pathlib import Path
from collections import Counter
from typing import Optional

try:
    import numpy as np
except ImportError:
    np = None
    print("  [!] numpy 未安装 (pip install numpy)，部分统计功能降级", file=sys.stderr)

# ─── 表层特征提取 ──────────────────────────────────────────

class SurfaceDistiller:
    """表层蒸馏：stylometry 统计特征，不需要 LLM"""

    def extract(self, text: str) -> dict:
        sentences = self._split_sentences(text)
        words = text.split()
        paragraphs = [p for p in text.split('\n\n') if p.strip()]

        # 句子级特征
        sent_lengths = [len(s.split()) for s in sentences] if sentences else [0]
        # 段落级特征
        para_lengths = [len(p.split()) for p in paragraphs] if paragraphs else [0]
        # 对话检测
        dialogue_lines = [l for l in text.split('\n') if l.strip().startswith('"') or l.strip().startswith('「')]
        dialogue_ratio = len(dialogue_lines) / max(len(text.split('\n')), 1)

        # 词频特征（去掉极短词）
        word_lengths = [len(w) for w in words if len(w) > 1]
        # 标点密度
        punct_count = sum(1 for c in text if c in '，。！？；：、！？,.;:!?')
        punct_density = punct_count / max(len(text), 1)

        # 人称检测
        first_person = len(re.findall(r'\b我\b|\b我们\b|\bI\b|\bwe\b', text))
        third_person = len(re.findall(r'\b他\b|\b她\b|\b它\b|\b他们\b|\b她们\b|\bhe\b|\bshe\b|\bthey\b', text))
        total_ref = first_person + third_person
        first_person_ratio = first_person / max(total_ref, 1)

        # 感官通道检测
        visual_words = len(re.findall(r'看[见到]?|目光|眼神|颜色|光|阴影|形状|look|see|gaze|color|light', text, re.IGNORECASE))
        auditory_words = len(re.findall(r'听[见到]?|声音|脚步声|呼吸声|he[a]?r|sound|voice|footstep', text, re.IGNORECASE))
        tactile_words = len(re.findall(r'触[摸到]?|温度|冷|热|粗糙|柔软|touch|cold|warm|rough|soft', text, re.IGNORECASE))
        total_sense = visual_words + auditory_words + tactile_words
        sense_distribution = {
            "visual": round(visual_words / max(total_sense, 1), 2),
            "auditory": round(auditory_words / max(total_sense, 1), 2),
            "tactile": round(tactile_words / max(total_sense, 1), 2),
        } if total_sense > 0 else {"visual": 0.34, "auditory": 0.33, "tactile": 0.33}

        # 节奏特征：句长变异系数
        mean_sl = float(np.mean(sent_lengths)) if np else (sum(sent_lengths)/max(len(sent_lengths),1))
        std_sl = float(np.std(sent_lengths)) if np and len(sent_lengths) > 1 else 0
        cv = round(std_sl / max(mean_sl, 0.01), 2) if mean_sl > 0 else 0.5

        return {
            "rhythm": {
                "mean_sentence_length": round(mean_sl, 1),
                "sentence_length_cv": cv,
                "short_sentence_ratio": round(sum(1 for s in sentences if len(s.split()) <= 5) / max(len(sentences), 1), 2),
                "long_sentence_ratio": round(sum(1 for s in sentences if len(s.split()) >= 25) / max(len(sentences), 1), 2),
                "mean_paragraph_length": round(float(np.mean(para_lengths)) if np else (sum(para_lengths)/max(len(para_lengths),1)), 1),
            },
            "voice": {
                "first_person_ratio": round(first_person_ratio, 2),
                "dialogue_ratio": round(dialogue_ratio, 2),
                "punct_density": round(punct_density, 3),
            },
            "sensory": {
                "distribution": sense_distribution,
                "dominant_channel": max(sense_distribution, key=sense_distribution.get),
            },
            "word_profile": {
                "mean_word_length": round(float(np.mean(word_lengths)), 1) if np and word_lengths else round(sum(word_lengths)/max(len(word_lengths),1), 1),
                "lexical_diversity": round(len(set(words)) / max(len(words), 1), 3),
            },
            "summary": {
                "total_chars": len(text),
                "total_sentences": len(sentences),
                "total_paragraphs": len(paragraphs),
            }
        }

    def _split_sentences(self, text: str) -> list:
        """中文 + 英文分句"""
        text = re.sub(r'\n+', ' ', text)
        raw = re.split(r'[。！？！？.!?\n]+', text)
        return [s.strip() for s in raw if len(s.strip()) > 3]


# ─── 中层结构提取（需 LLM） ──────────────────────────────

class StructuralDistiller:
    """中层蒸馏：情节结构、情感弧线、人物网络——需要 LLM 调用"""

    SYSTEM_PROMPT = """你是一个叙事分析专家。提取给定文本的结构化叙事特征。
输出必须是纯 JSON，不要额外说明。"""

    ANALYSIS_TEMPLATE = """分析以下文本，提取结构化叙事特征：

文本内容：
{text}

请输出 JSON，包含以下字段：
1. plot_structure: {{
    "has_three_act": bool,  // 是否能识别出明显的三幕结构
    "act_breaks": [  // 如果可识别，每一幕的结束位置（字符偏移）
        {{"act": 1, "position": int, "description": "简短说明"}}
    ],
    "turning_points": [  // 明显的转折点
        {{"position": int, "type": "秘密揭露|角色反转|假胜利|外力介入|代价显现|认知升级", "description": "简短说明"}}
    ]
}}
2. emotional_arc: {{
    "dominant_tone": "冷峻写实|温暖治愈|黑色幽默|悬疑暗流|诗意思辨|激烈狂暴",
    "tone_curve": [{{"position": int, "intensity": 1-10, "valence": "positive|negative|neutral"}}],  // 4-6个采样点
    "arc_type": "从失去到重建|从天真到幻灭|从愧疚到救赎|从恐惧到勇气|从孤独到连接|从服从到自主|复合型"
}}
3. characters: [
    {{
        "name": "角色名或代号",
        "role": "主角|配角|反派|导师|盟友",
        "arc": "角色在这段文本中的变化",
        "interactions": ["与其他角色的关系"]
    }}
]
4. conflict_profile: {{
    "primary_type": "身份冲突|资源冲突|价值观冲突|关系冲突|生存冲突|认知冲突",
    "secondary_types": [],
    "internal_vs_external": float  // 0=纯外部冲突, 1=纯内部冲突
}}
5. narrative_pace: {{
    "overall": "缓慢|中等|快速|紧凑",
    "scene_vs_summary": float  // 0=纯概述, 1=纯场景
}}"""

    def __init__(self, llm_call_fn=None):
        self.llm_call = llm_call_fn

    def extract(self, text: str) -> dict:
        if not self.llm_call:
            return {"_note": "需要 LLM API 才能运行", "_text_length": len(text)}
        try:
            prompt = self.ANALYSIS_TEMPLATE.format(text=text[:8000])
            result = self.llm_call(self.SYSTEM_PROMPT, prompt, temp=0.3)
            return self._parse_json(result)
        except Exception as e:
            return {"_error": str(e), "_text_length": len(text)}

    def _parse_json(self, raw: str) -> dict:
        """从 LLM 回复中提取 JSON"""
        # Try direct parse
        try:
            return json.loads(raw)
        except:
            pass
        # Try find JSON block
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except:
                pass
        # Try find first { ... }
        m = re.search(r'(\{.*\})', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except:
                pass
        return {"_parse_error": "无法解析 LLM 输出", "_raw_preview": raw[:200]}


# ─── 联合蒸馏器 ────────────────────────────────────────────

class Distiller:
    """联合表层 + 中层蒸馏，输出完整的风格档案"""

    def __init__(self, llm_call_fn=None):
        self.surface = SurfaceDistiller()
        self.structural = StructuralDistiller(llm_call_fn)

    def distill(self, text: str, source_name: str = "") -> dict:
        """执行完整蒸馏，返回风格档案增量"""
        surface = self.surface.extract(text)
        structural = self.structural.extract(text)

        result = {
            "source": source_name or "未命名文本",
            "surface": surface,
            "structural": structural,
            "merged_profile": self._merge(surface, structural),
            "distilled_at": self._now(),
        }
        return result

    def _merge(self, surface: dict, structural: dict) -> dict:
        """合并为可用于发散引擎的约束参数"""
        rhythm = surface.get("rhythm", {})
        voice = surface.get("voice", {})
        sensory = surface.get("sensory", {})

        # 节奏分类
        cv = rhythm.get("sentence_length_cv", 0.5)
        if cv > 1.0:
            pace = "剧烈起伏"
        elif cv > 0.6:
            pace = "张弛交替"
        else:
            pace = "均匀稳定"

        # 对话倾向
        dialogue_ratio = voice.get("dialogue_ratio", 0)
        if dialogue_ratio > 0.5:
            narrative_mode = "对话驱动"
        elif dialogue_ratio > 0.2:
            narrative_mode = "叙事为主有对话"
        else:
            narrative_mode = "纯叙事"

        # 首选调性（来自 LLM 结构分析或推算）
        preferred_tone = structural.get("emotional_arc", {}).get("dominant_tone", "")

        return {
            "rhythm_profile": {
                "pace_label": pace,
                "mean_sentence_length": rhythm.get("mean_sentence_length", 15),
                "paragraph_style": "短段落密集" if rhythm.get("mean_paragraph_length", 100) < 50 else "长段落舒展",
            },
            "voice_profile": {
                "narrative_mode": narrative_mode,
                "perspective": "第一人称偏多" if voice.get("first_person_ratio", 0) > 0.5 else "第三人称偏多",
                "sensory_dominant": sensory.get("dominant_channel", "visual"),
            },
            "preferred_tone": preferred_tone or "悬疑暗流",
            "conflict_bias": structural.get("conflict_profile", {}).get("primary_type", "关系冲突"),
            "internal_external_balance": structural.get("conflict_profile", {}).get("internal_vs_external", 0.5),
            "structural_features": {
                "has_clear_three_act": structural.get("plot_structure", {}).get("has_three_act", False),
                "turning_point_count": len(structural.get("plot_structure", {}).get("turning_points", [])),
            }
        }

    def _now(self):
        from datetime import datetime
        return datetime.now().isoformat()


# ─── CLI ────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Æsir 蒸馏管道")
    parser.add_argument('--file', '-f', help='输入文本文件路径')
    parser.add_argument('--text', '-t', help='直接输入文本')
    parser.add_argument('--server', '-s', action='store_true', help='启动 API 服务')
    parser.add_argument('--port', type=int, default=8765, help='API 端口')
    parser.add_argument('--llm', action='store_true', help='启用 LLM 中层分析')
    parser.add_argument('--output', '-o', default='', help='输出文件路径')
    args = parser.parse_args()

    text = ""
    source = ""

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"文件不存在: {args.file}")
            sys.exit(1)
        raw_bytes = path.read_bytes()
        try:
            text = raw_bytes.decode('utf-8')
        except:
            text = raw_bytes.decode('utf-8', errors='replace')
        source = path.name

    elif args.text:
        text = args.text
        source = "直接输入"

    elif args.server:
        run_server(args.port, args.llm)
        return

    else:
        # 交互模式
        print("✦ Æsir 蒸馏管道 — 输入文本（Ctrl+D 结束）:")
        text = sys.stdin.read()
        source = "标准输入"

    if not text.strip():
        print("没有输入文本。")
        sys.exit(1)

    # LLM 回调
    llm_fn = None
    if args.llm:
        def llm_call(system, user, temp=0.8):
            api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("需要设置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY", file=sys.stderr)
                return json.dumps({"error": "no_api_key"})
            # Try Anthropic
            import urllib.request
            if os.environ.get("ANTHROPIC_API_KEY"):
                try:
                    data = json.dumps({"model":"claude-sonnet-4-20250514","max_tokens":4096,"temperature":temp,"system":system,"messages":[{"role":"user","content":user[:12000]}]}).encode()
                    req = urllib.request.Request("https://api.anthropic.com/v1/messages",data=data,headers={"Content-Type":"application/json","x-api-key":api_key,"anthropic-version":"2023-06-01"})
                    with urllib.request.urlopen(req,timeout=120) as resp:
                        return json.loads(resp.read())["content"][0]["text"]
                except Exception as e:
                    print(f"Anthropic 失败: {e}", file=sys.stderr)
            # Fallback OpenAI
            try:
                data = json.dumps({"model":"gpt-4o-mini","max_tokens":4096,"temperature":temp,"messages":[{"role":"system","content":system},{"role":"user","content":user[:12000]}]}).encode()
                req = urllib.request.Request("https://api.openai.com/v1/chat/completions",data=data,headers={"Content-Type":"application/json","Authorization":f"Bearer {api_key}"})
                with urllib.request.urlopen(req,timeout=120) as resp:
                    return json.loads(resp.read())["choices"][0]["message"]["content"]
            except Exception as e:
                return json.dumps({"error":str(e)})
        llm_fn = llm_call

    distiller = Distiller(llm_fn=llm_fn)
    print(f"\n⟡ 正在蒸馏: {source} ({len(text)} 字符)\n", file=sys.stderr)
    result = distiller.distill(text, source)

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"结果已写入: {args.output}")
    else:
        print(output)


def run_server(port=8765, enable_llm=False):
    """启动轻量 API 服务，供前端调用"""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
    except ImportError:
        print("需要 Python 标准库 http.server")
        sys.exit(1)

    class DistillHandler(BaseHTTPRequestHandler):
        llm_fn = None

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == '/distill':
                try:
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    text = data.get('text', '')
                    source = data.get('source', 'API 调用')

                    if not text.strip():
                        self._json(400, {"error": "text 不能为空"})
                        return

                    # 判断是否启用 LLM
                    use_llm = data.get('use_llm', enable_llm)
                    llm_fn = self.llm_fn if use_llm else None

                    distiller = Distiller(llm_fn=llm_fn)
                    # 对长文本截断（LLM 分析限制）
                    if use_llm and len(text) > 15000:
                        text = text[:15000] + "\n\n[文本过长，已截断...]"

                    result = distiller.distill(text, source)
                    self._json(200, result)

                except Exception as e:
                    self._json(500, {"error": str(e)})

            elif path == '/health':
                self._json(200, {"status": "ok", "llm_available": enable_llm})
            else:
                self._json(404, {"error": "not_found"})

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

    DistillHandler.llm_fn = llm_fn
    server = HTTPServer(('0.0.0.0', port), DistillHandler)
    print(f"✦ Æsir 蒸馏 API 运行在 http://localhost:{port}")
    print(f"  POST /distill  — 提交文本蒸馏")
    print(f"  GET  /health   — 健康检查")
    print(f"  LLM 中层分析: {'开启' if enable_llm else '关闭（表层统计 only）'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n关闭服务器")
        server.server_close()


if __name__ == "__main__":
    main()
