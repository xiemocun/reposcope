"""reposcope 的测试：地图的定位信息必须是真的，MCP 协议必须能握手。"""
import json
import os
import subprocess
import sys
import textwrap

import reposcope


def _mk_repo(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "core.py").write_text(
        "def alpha():\n    pass\n\nclass Beta:\n    pass\n" * 40, encoding="utf-8")
    (tmp_path / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("ignored", encoding="utf-8")
    return tmp_path


def test_map_counts_only_matching_extensions(tmp_path):
    m = reposcope.build_map(str(_mk_repo(tmp_path)), {".py"})
    assert m["files"] == 2, m
    assert m["loc_total"] > 100
    assert any(p.endswith("core.py") for p in [f["path"] for f in m["largest"]])


def test_entry_candidates_are_named_like_entries(tmp_path):
    m = reposcope.build_map(str(_mk_repo(tmp_path)), {".py"})
    assert "main.py" in m["entry_candidates"], m["entry_candidates"]


def test_symbols_are_counted(tmp_path):
    m = reposcope.build_map(str(_mk_repo(tmp_path)), {".py"})
    top = m["most_symbols"][0]
    assert top["symbols"] > 0
    assert "alpha" in top["top"]


def test_empty_dir_does_not_crash(tmp_path):
    m = reposcope.build_map(str(tmp_path), {".py"})
    assert m["files"] == 0


def _speak(messages):
    reqs = "\n".join(json.dumps(m) for m in messages) + "\n"
    out = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "mcp_server.py")],
        input=reqs, capture_output=True, text=True, timeout=60)
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def test_mcp_handshake_and_tool_call(tmp_path):
    repo = str(_mk_repo(tmp_path))
    resps = _speak([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"arguments": {"repo": repo, "ext": ".py"}}},
    ])
    by_id = {r.get("id"): r for r in resps}
    assert by_id[1]["result"]["serverInfo"]["name"] == "reposcope"
    assert [t["name"] for t in by_id[2]["result"]["tools"]] == ["repo_map"]
    payload = json.loads(by_id[3]["result"]["content"][0]["text"])
    assert payload["files"] == 2


def test_unknown_method_returns_jsonrpc_error():
    resps = _speak([{"jsonrpc": "2.0", "id": 9, "method": "nope"}])
    assert resps[0]["error"]["code"] == -32601