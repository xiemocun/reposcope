"""reposcope：给 AI 用的仓库地图。

人不读它的输出，模型读。目标是让 agent 在花 token 读代码之前，
先知道「这个仓库由什么构成、该从哪几个文件开始、哪些地方最近在动」。

输出是紧凑 JSON，不含散文，不返回源码正文——只有定位信息。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache"}
DEF_RE = re.compile(r"^(?:def|class|func|type|func \()\s+([A-Za-z_]\w*)", re.M)


def churn(repo: str) -> dict[str, int]:
    """最近 200 次提交里，每个文件被改了几次——热点的代理指标。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "-200", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception:
        return {}
    counts: dict[str, int] = {}
    for line in out.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    return counts


def scan(repo: str, exts: set[str], max_files: int = 4000) -> list[dict]:
    ch = churn(repo)
    files = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext not in exts:
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, repo)
            try:
                if os.path.getsize(path) > 2_000_000:
                    continue
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except OSError:
                continue
            lines = text.count("\n") + 1
            symbols = DEF_RE.findall(text)
            files.append({
                "path": rel,
                "loc": lines,
                "symbols": len(symbols),
                "top": symbols[:5],
                "churn": ch.get(rel, 0),
            })
            if len(files) >= max_files:
                break
        if len(files) >= max_files:
            break
    return files


def build_map(repo: str, exts: set[str]) -> dict:
    files = scan(repo, exts)
    if not files:
        return {"repo": repo, "files": 0, "note": "no matching files"}

    total_loc = sum(f["loc"] for f in files)
    # 三条排序轴：体量、符号密度、改动频率。agent 按需要选一条。
    by_size = sorted(files, key=lambda f: f["loc"], reverse=True)[:12]
    by_churn = sorted(files, key=lambda f: (f["churn"], f["loc"]), reverse=True)[:12]
    by_symbols = sorted(files, key=lambda f: f["symbols"], reverse=True)[:12]

    # 入口候选：名字里带 main/cli/index/app 的
    entries = [f["path"] for f in files
               if re.search(r"(^|/)(main|cli|index|app|__main__)\.", f["path"])][:8]

    return {
        "repo": os.path.abspath(repo),
        "files": len(files),
        "loc_total": total_loc,
        "entry_candidates": entries,
        "largest": [{"path": f["path"], "loc": f["loc"]} for f in by_size],
        "most_changed": [{"path": f["path"], "churn": f["churn"]} for f in by_churn],
        "most_symbols": [{"path": f["path"], "symbols": f["symbols"], "top": f["top"]}
                         for f in by_symbols],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--ext", default=".py,.go,.rs,.ts,.js,.java,.c,.cpp,.h")
    a = ap.parse_args()
    exts = {e.strip().lower() for e in a.ext.split(",") if e.strip()}
    print(json.dumps(build_map(a.repo, exts), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()