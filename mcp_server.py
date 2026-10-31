"""reposcope 的 MCP 服务：让 agent 直接调用，而不是人去敲命令行。

stdio + 换行分隔的 JSON-RPC 2.0，实现三个方法：
  initialize / tools/list / tools/call

暴露一个工具 repo_map(repo, ext) → 紧凑 JSON 的仓库地图。
"""
from __future__ import annotations

import json
import sys

import reposcope

PROTOCOL = "2025-06-18"

TOOL = {
    "name": "repo_map",
    "description": (
        "Map a repository before reading it. Returns compact JSON: file count, "
        "total LOC, entry-point candidates, and the twelve largest / most-churned / "
        "most-symbol-dense files. No source text is returned."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "repository path"},
            "ext": {"type": "string", "description": "comma separated extensions",
                    "default": ".py,.go,.rs,.ts,.js,.java,.c,.cpp,.h"},
        },
        "required": ["repo"],
    },
}


def handle(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "reposcope", "version": "0.1.0"},
        }}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        params = req.get("params") or {}
        args = params.get("arguments") or {}
        repo = args.get("repo", ".")
        ext = args.get("ext", TOOL["inputSchema"]["properties"]["ext"]["default"])
        try:
            data = reposcope.build_map(repo, {e.strip().lower() for e in ext.split(",") if e.strip()})
            text = json.dumps(data, ensure_ascii=False)
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": f"error: {exc}"}],
                               "isError": True}}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()