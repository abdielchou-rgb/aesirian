"""文鉴 Analyzer V2 — 零 API Key 纯启发式多维文本分析引擎。"""
import re
from collections import Counter
from typing import Any

VALUE_PAIRS = {
    "希望": ["希望","期待","憧憬","指望","盼"],"绝望": ["绝望","放弃","无望","灰心","死心"],
    "爱": ["爱","温柔","心疼","深情","呵护"],"恨": ["恨","愤怒","痛恨","憎恨","怨恨"],
    "信任": ["信任","信赖","相信","可靠","放心"],"背叛": ["背叛","出卖","告密","反水","背弃"],
    "真相": ["真相","发现","揭穿","暴露","识破"],"谎言": ["谎言","欺骗","隐瞒","伪装","假话"],
    "生": ["生","活","生存","活着","救"],"死": ["死","亡","杀","灭","葬"],
    "自由": ["自由","解放","挣脱","逃脱","解脱"],"束缚": ["束缚","囚禁","困住","限制","牢笼"],
    "勇敢": ["勇敢","无畏","挺身","直面","不退"],"怯懦": ["怯懦","恐惧","退缩","发抖","害怕"],
    "和解": ["和解","原谅","谅解","和好","释然"],"决裂": ["决裂","翻脸","断绝","决绝","一刀两断"],
    "力量": ["力量","实力","强大","境界","突破"],"弱小": ["弱小","无力","凡人","蝼蚁","废柴"],
}
TOUCHPOINT_KEYWORDS = {
    "肢体": ["手","指节","拳头","手指","手掌","脚步","腿","肩膀","指尖","手腕"],
    "眼神": ["目光","眼神","视线","凝视","垂眼","抬眼","注视","盯","瞥"],
    "表情": ["沉默","停","僵","顿","愣","怔","颤","抿","咬","绷"],
    "动作": ["握","抬头","低头","转身","攥","捏","抱","推","拉","敲","拍"],
    "器物": ["杯","桌","窗","门","手中","口袋里","剑","刀","笔墨","信"],
}
GAP_MARKERS = ["但是","然而","没想到","却","竟","出乎","突然","原来","可是","但","偏偏","岂料","谁知","不料"]
HOOK_MARKERS = ["突然","但是","然而","没想到","却发现","竟","原来","为什么","怎么回事","来不及","有件事","你知"]
EMOTION_WORDS = ["感到","觉得","愤怒","悲伤","恐惧","喜悦","痛苦","惊慌","兴奋","沮丧","焦虑","欣慰","绝望","感动","不安"]
PLEASURE_MARKERS = {
    "打脸": ["打脸","震惊","目瞪口呆","难以置信","倒吸","这才知道","竟然这么","原来他"],
    "升级": ["突破","晋级","进阶","升级","瓶颈","顿悟","突破境界"],
    "奇遇": ["机缘","奇遇","秘境","传承","意外获得"],
    "逆袭": ["反击","翻盘","绝境","逆转","逆袭"],
    "装逼": ["淡淡","随意","不经意","随手","轻描淡写","漫不经心","云淡风轻"],
}
STAKES_MARKERS = ["失去","如果失败","代价","后果","赌上","拼了","不惜","唯一的","最后的机会","再也","覆灭","绝路"]
ADVERB_PATTERN = re.compile(r'[一-鿿]+地')
PASSIVE_EXCLUDE = {"被子", "被动", "被告", "被迫", "被捕", "被称为", "被称作"}
PASSIVE_PATTERN = re.compile(r'被[一-鿿]{2,}')

def _count_passive(text: str) -> int:
    """统计被动语态，排除词典中的非被动用法。"""
    count = 0
    for m in PASSIVE_PATTERN.finditer(text):
        matched = m.group()
        if not any(matched.startswith(ex) for ex in PASSIVE_EXCLUDE):
            count += 1
    return count
FILLER_PATTERN = re.compile(r'(基本上|实际上|非常|真的|有点|某种|似乎|好像|几乎|开始|然后|于是|接着)')
DIALOGUE_LINE = re.compile(r'[「『"\'][^」』"\']+[」』"\']')

class LocalAnalyzer:
    def analyze_chapter(self, text, chapter_index=0, title=""):
        lines = [l for l in text.split("\n") if l.strip()]
        paragraphs = [l for l in text.split("\n") if l.strip() and len(l) > 20]
        _chars = len(text)
        emotions = self._count_emotions(text)
        touchpoints = self._count_touchpoints(text)
        gaps = self._count_gaps(text)
        entry_val, exit_val = self._estimate_scene_values(text)
        hook_pos = self._find_first_hook(text)
        dialogue_lines = self._count_dialogues(text)
        characters = self._extract_names(text)

        pleasure = self._detect_pleasure_points(text)
        chapter_end_force = self._chapter_end_force(text)
        scene_beats = self._detect_scene_beats(text, paragraphs)
        stakes = self._detect_stakes(text)
        micro_tension = self._micro_tension_analysis(text, paragraphs)
        adverb_count = len(ADVERB_PATTERN.findall(text))
        passive_count = _count_passive(text)
        filler_count = len(FILLER_PATTERN.findall(text))
        hook_density = self._hook_density(text)
        hook_distribution = self._hook_distribution(text)

        result = {
            "chapter_index": chapter_index, "title": title,
            "word_count": _chars, "char_count": _chars,
            "line_count": len(lines), "paragraph_count": len(paragraphs),
            "direct_emotions": emotions, "touchpoints": touchpoints,
            "emotion_to_touchpoint_ratio": round(emotions / max(touchpoints, 1), 2),
            "entry_value": entry_val, "exit_value": exit_val,
            "scene_flipped": entry_val != exit_val,
            "gap_count": gaps["total"], "gap_density": gaps["density"],
            "gap_intensities": gaps["intensities"],
            "words_since_last_gap": gaps["words_since_last"],
            "first_hook_position": hook_pos, "has_hook": hook_pos < 99999,
            "character_count": len(characters),
            "dialogue_lines": dialogue_lines,
            "dialogue_density": round(dialogue_lines / max(len(lines), 1), 2),
            "pleasure_points": pleasure,
            "pleasure_density": round(sum(pleasure.values()) / max(_chars / 1000, 1), 2),
            "chapter_end_force": chapter_end_force,
            "scene_beats": scene_beats,
            "stakes": stakes, "has_stakes": stakes["count"] > 0,
            "micro_tension": micro_tension,
            "adverb_count": adverb_count,
            "adverb_density": round(adverb_count / max(_chars / 100, 1), 2),
            "passive_count": passive_count,
            "passive_density": round(passive_count / max(_chars / 100, 1), 2),
            "filler_count": filler_count,
            "filler_density": round(filler_count / max(_chars / 100, 1), 2),
            "hook_density": hook_density,
            "hook_distribution": hook_distribution,
        }
        return result

    def analyze_full_manuscript(self, chapters):
        all_r = [self.analyze_chapter(ch["text"], i, ch.get("title","")) for i,ch in enumerate(chapters)]
        if not all_r: return {"total_chapters":0}
        ctx = {
            "total_chapters": len(chapters), "total_chars": sum(r["char_count"] for r in all_r),
            "chapter_results": all_r, "gap_densities": [r["gap_density"] for r in all_r],
            "gap_intensities": [r["gap_intensities"] for r in all_r],
            "value_pair_counts": Counter(),
            "pleasure_points_total": sum(sum(r["pleasure_points"].values()) for r in all_r),
            "stakes_total": sum(r["stakes"]["count"] for r in all_r),
            "avg_hook_density": round(sum(r["hook_density"] for r in all_r)/max(len(all_r),1), 2),
            "avg_adverb_density": round(sum(r["adverb_density"] for r in all_r)/max(len(all_r),1), 2),
            "avg_passive_density": round(sum(r["passive_density"] for r in all_r)/max(len(all_r),1), 2),
        }
        for r in all_r:
            if r["entry_value"] != "未知" and r["exit_value"] != "未知":
                pair = r['entry_value'] + "->" + r['exit_value']
                ctx["value_pair_counts"][pair] = ctx["value_pair_counts"].get(pair, 0) + 1
        return ctx

    def _count_emotions(self, text): return sum(text.count(w) for w in EMOTION_WORDS)
    def _count_touchpoints(self, text):
        c = 0
        for _, words in TOUCHPOINT_KEYWORDS.items(): c += sum(text.count(w) for w in words)
        return c
    def _count_gaps(self, text):
        count = sum(1 for m in GAP_MARKERS for _ in re.finditer(re.escape(m), text))
        paras = text.split("\n\n"); cg = 0
        for p in paras:
            if any(m in p for m in GAP_MARKERS): cg = 0
            else: cg += len(p)
        return {"total": count, "density": round(count/max(len(text)/1000,1),2),
                "intensities": [1]*count if count<10 else [2]*(count//2)+[1]*(count-count//2),
                "words_since_last": cg}
    def _estimate_scene_values(self, text):
        third = max(len(text)//3, 1); first = text[:third]; last = text[-third:]
        fs, ls = Counter(), Counter()
        for v, ks in VALUE_PAIRS.items():
            fs[v] = sum(first.count(k) for k in ks)
            ls[v] = sum(last.count(k) for k in ks)
        e = fs.most_common(1)[0][0] if fs and fs.most_common(1)[0][1]>0 else "未知"
        x = ls.most_common(1)[0][0] if ls and ls.most_common(1)[0][1]>0 else "未知"
        return e, x
    def _find_first_hook(self, text):
        hooks = HOOK_MARKERS + ["什么","为什么","怎么回事","你是谁","杀","死","追","逃","别走"]
        fp = 99999
        for h in hooks:
            p = text.find(h)
            if 0 < p < fp: fp = p
        return fp
    def _extract_names(self, text): return list(set(re.findall(r'[「『]([^」』]{2,3})[」』]', text)))
    def _count_dialogues(self, text): return len(DIALOGUE_LINE.findall(text))
    def _detect_pleasure_points(self, text):
        return {pt: sum(text.count(kw) for kw in kws) for pt, kws in PLEASURE_MARKERS.items()}
    def _chapter_end_force(self, text):
        if len(text) < 200: return {"length": len(text), "force": "insufficient", "signals": [], "has_cliffhanger": False}
        tail = text[-300:] if len(text) >= 300 else text; signals = []
        if any(w in tail for w in ["来不及","追上","包围","逼近","危险","生死"]): signals.append("crisis")
        if any(w in tail for w in ["发现","揭穿","暴露","竟然是","原来"]): signals.append("discovery")
        if any(w in tail for w in ["决定","我要","必须","一定要"]): signals.append("decision")
        if any(w in tail for w in ["不知道","谁能","到底","难道是","你知","什么"]): signals.append("suspense")
        if any(w in tail for w in ["有件事","有个秘密","其实","真相"]): signals.append("before_turn")
        return {"length": min(len(text),300), "force": "strong" if len(signals)>=2 else "moderate" if len(signals)==1 else "weak", "signals": signals, "has_cliffhanger": len(signals)>=1}
    def _detect_scene_beats(self, text, paragraphs):
        beats = []
        for i, para in enumerate(paragraphs):
            pp = round(i/max(len(paragraphs),1)*100,0); bt = "narration"
            if any(m in para for m in GAP_MARKERS): bt = "disaster"
            elif any(p in para for p in ["决定","选择","于是","既然如此"]): bt = "decision"
            elif any(w in para for w in ["感到","觉得","难过","痛苦","恐惧"]): bt = "reaction"
            elif any(p in para for p in ["怎么办","如何","困境"]): bt = "dilemma"
            elif DIALOGUE_LINE.search(para): bt = "dialogue"
            beats.append({"position_pct": pp, "beat_type": bt})
        types = [b["beat_type"] for b in beats]
        has_conf, has_react = "disaster" in types, "reaction" in types
        return {"beat_types": list(set(types)), "has_scene_structure": has_conf,
                "has_sequel_structure": has_react or "decision" in types,
                "has_complete_scene_sequel": has_conf and has_react,
                "beat_sequence": "scene_sequel" if has_conf and has_react else "narration_only"}
    def _detect_stakes(self, text):
        count = sum(text.count(m) for m in STAKES_MARKERS)
        return {"count": count, "density": round(count/max(len(text)/1000,1), 2)}
    def _micro_tension_analysis(self, text, paragraphs):
        if len(paragraphs) < 3: return {"tension_variance": 0, "high_tension_segments": 0, "low_tension_segments": 0}
        scores = []
        for para in paragraphs:
            s = 0.0
            s += sum(1 for m in GAP_MARKERS if m in para) * 2
            s += sum(1 for m in HOOK_MARKERS if m in para) * 1.5
            s += len(DIALOGUE_LINE.findall(para)) * 0.5
            s += sum(1 for m in EMOTION_WORDS if m in para) * 1.0
            scores.append(s / max(len(para)/100, 1))
        avg = sum(scores)/len(scores); var = sum((s-avg)**2 for s in scores)/len(scores)
        high = sum(1 for s in scores if s > avg*1.5); low = sum(1 for s in scores if s < avg*0.5)
        return {"tension_variance": round(var,2), "high_tension_segments": high, "low_tension_segments": low, "is_flat": high==0 and low==0}
    def _hook_density(self, text):
        return round(sum(text.count(h) for h in HOOK_MARKERS)/max(len(text)/1000,1), 2)
    def _hook_distribution(self, text):
        sl = max(len(text)//5, 1); segs = []
        for i in range(5):
            seg = text[i*sl:(i+1)*sl] if i<4 else text[i*sl:]
            segs.append({"segment": i+1, "start_char": i*sl,
                         "hook_count": sum(seg.count(h) for h in HOOK_MARKERS),
                         "hook_density": round(sum(seg.count(h) for h in HOOK_MARKERS)/max(len(seg)/1000,1), 2)})
        return segs

analyzer = LocalAnalyzer()