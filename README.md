# reposcope

**给 AI 用的仓库地图。** 人看着难受，模型看着正好。

## 问题

一个真实项目的源码塞不进任何上下文窗口。以 Soup 为例：1789 个 Python 文件、73 万行。agent 想动它，只能盲猜从哪读起，猜错就白烧几万 token。

## 它做什么

一条命令（或一次工具调用），把仓库压成 2KB 的结构化地图：

```json
{
  "files": 1789,
  "loc_total": 737313,
  "entry_candidates": ["src/soup_cli/cli.py", "src/soup_cli/__main__.py"],
  "largest": [{"path": "config/schema.py", "loc": 10000}],
  "most_changed": [{"path": "...", "churn": 34}],
  "most_symbols": [{"path": "...", "symbols": 210, "top": ["main", "run"]}]
}
```

**不返回源码正文。** 只给定位信息。

## 三条轴拆开，不合并成一个分数

| 轴 | 什么时候用 |
|---|---|
| `largest` | 想理解架构 |
| `most_changed` | 想知道哪里脆弱、哪里在演进 |
| `most_symbols` | 想找公共 API |

agent 的任务不同，需要的入口不同，所以不给一个「重要性排序」。

## 两种用法

**命令行：**

```bash
python reposcope.py /path/to/repo --ext .py,.go
```

**作为 MCP 工具**（任何支持 MCP 的 agent 都能直接调）：

```json
{"mcpServers": {"reposcope": {"command": "python", "args": ["/path/to/mcp_server.py"]}}}
```

暴露一个工具 `repo_map(repo, ext)`，stdio + 换行分隔的 JSON-RPC。

## 已验证

- 握手：`initialize` 返回协议版本与服务器信息
- 工具发现：`tools/list` 返回 `repo_map`
- 工具调用：对真实仓库返回 1789 文件 / 737313 行的地图
- 6 个单元测试：扩展名过滤、入口识别、符号统计、空目录、握手、未知方法

## 局限

- 符号识别靠正则，覆盖 Python/Go/Rust/JS 的常见定义形式，不做真正的语法解析
- 文件超过 2 MB 跳过（生成的产物、数据文件）
- 热区按最近 200 次提交算，克隆太浅时会退化成按体量排