"""示例 analyzer 插件：标点情绪密度"""


class ExclamationAnalyzer:
    def analyze(self, text: str) -> dict:
        n = max(len(text), 1)
        return {
            "exclamation_per_1k": round(text.count("！") / n * 1000, 2),
            "question_per_1k": round(text.count("？") / n * 1000, 2),
        }