"""
#22 MCP Server Tests — dispatch layer (JSON-RPC 2.0)
Run: python -X utf8 -m pytest tests/test_mcp_server.py -q
"""
import json
import sys

sys.path.insert(0, ".")

from mcp_server import dispatch_request, TOOL_HANDLERS


def rpc(msg: dict) -> dict | None:
    resp = dispatch_request(msg)
    return json.loads(resp) if resp else None


class TestMCPServer:
    def test_initialize(self):
        r = rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r["result"]["serverInfo"]["name"] == "aesirian"
        assert "tools" in r["result"]["capabilities"]
        print("[OK] initialize handshake")

    def test_tools_list(self):
        r = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = r["result"]["tools"]
        names = [t["name"] for t in tools]
        assert len(tools) == 8
        for expected in ("analyze_chapter", "style_fingerprint", "simulate",
                         "diverge", "tom_query", "list_projects",
                         "generate", "export_markdown"):
            assert expected in names
        # 每个 schema 都是合法 JSON Schema 骨架
        for t in tools:
            assert "inputSchema" in t and t["inputSchema"]["type"] == "object"
        print(f"[OK] tools/list: {len(tools)} tools")

    def _call(self, name, args):
        r = rpc({"jsonrpc": "2.0", "id": 99, "method": "tools/call",
                 "params": {"name": name, "arguments": args}})
        assert "error" not in r, str(r)
        return json.loads(r["result"]["content"][0]["text"])

    def test_analyze_chapter(self):
        d = self._call("analyze_chapter", {"text": "夜色降临。他推开门，看见她在等他。两人对视，无言。窗外雨声渐大。"})
        assert "total_gates" in d and d["total_gates"] > 100
        print(f"[OK] analyze_chapter: {d['total_gates']} gates, {d['failed']} failed")

    def test_style_fingerprint(self):
        d = self._call("style_fingerprint", {
            "text": "夜色像墨一样浓。他推开沉重的木门，门轴发出刺耳的呻吟。月光落在她半边脸上。"
        })
        assert "radar" in d and len(d["radar"]["indicators"]) >= 6
        assert "sensory_radar" in d
        print(f"[OK] style_fingerprint: {len(d['radar']['indicators'])} radar dims")

    def test_list_projects(self):
        d = self._call("list_projects", {})
        assert "projects" in d and isinstance(d["projects"], list)
        print(f"[OK] list_projects: {len(d['projects'])} projects")

    def test_diverge(self):
        d = self._call("diverge", {"fragments": ["雨夜便利店", "无名信", "末班地铁"]})
        assert len(d["worldlines"]) == 5
        print(f"[OK] diverge: {len(d['worldlines'])} worldlines")

    def test_unknown_tool_error(self):
        r = rpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "nope", "arguments": {}}})
        assert r["error"]["code"] == -32601
        print("[OK] unknown tool -> -32601")

    def test_unknown_method_error(self):
        r = rpc({"jsonrpc": "2.0", "id": 4, "method": "bogus/method", "params": {}})
        assert r["error"]["code"] == -32601
        print("[OK] unknown method -> -32601")

    def test_notification_no_response(self):
        assert rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        print("[OK] notification returns None")

    def test_stdio_roundtrip(self):
        """真实 stdio 子进程往返一轮"""
        import subprocess
        req = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "mcp_server.py"],
            input=req, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        line = proc.stdout.strip().splitlines()[0]
        r = json.loads(line)
        assert r["id"] == 7 and len(r["result"]["tools"]) == 8
        print("[OK] stdio roundtrip works")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])