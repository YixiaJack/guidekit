"""PreToolUse hook: the hard boundary for every agent run.

Claude Code calls this before each tool call and blocks the call when we exit 2.
It fails closed: no policy, unreadable input or an unknown tool means "deny".

Policy (JSON file named by $GK_POLICY_FILE, written by trusted code per run):
  {"stage": "...", "cwd": "...", "read_roots": [...], "write_roots": [...]}

Rules:
  * Only Read / Glob / Grep / Write / Edit / MultiEdit exist for the agent.
    Everything else (Bash, WebFetch, WebSearch, Agent, any mcp__* connector...) is denied.
  * Reads must resolve (after ~ expansion and symlinks) inside read_roots or write_roots.
  * Glob/Grep patterns may not be absolute or climb with '..'.
  * Writes must resolve inside write_roots and may not go through a symlink.
Every decision is appended to logs/guard.jsonl.
"""
import json
import os
import sys
import time

LOG = os.environ.get("GK_GUARD_LOG") or os.path.join(os.path.expanduser("~"), ".guidekit", "guard.jsonl")
READ_TOOLS = {"Read", "Glob", "Grep"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def _log(entry):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        entry["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False)[:4000] + "\n")
    except Exception:
        pass


def deny(reason, ctx):
    ctx.update(decision="deny", reason=reason)
    _log(ctx)
    sys.stderr.write(f"[research-kb guard] 已拦截：{reason}。只能读写本次任务指定的目录，不能执行命令或联网。\n")
    sys.exit(2)


def allow(ctx):
    ctx["decision"] = "allow"
    _log(ctx)
    sys.exit(0)


def resolve(p, cwd):
    p = os.path.expanduser(str(p))
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.realpath(p)


def inside(path, roots):
    return any(path == r or path.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def bad_pattern(pat):
    if not pat:
        return False
    pat = str(pat)
    if pat.startswith(("/", "~", "\\")):
        return True
    return ".." in pat.replace("\\", "/").split("/")


def main():
    ctx = {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        deny("无法解析工具调用", ctx)
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    ctx.update(tool=tool, input={k: (str(v)[:300]) for k, v in ti.items() if k != "content"})

    pol_file = os.environ.get("GK_POLICY_FILE")
    if not pol_file:
        deny("没有安全策略文件", ctx)
    try:
        with open(pol_file, encoding="utf-8") as f:
            pol = json.load(f)
        read_roots = [os.path.realpath(r) for r in pol["read_roots"]]
        write_roots = [os.path.realpath(r) for r in pol["write_roots"]]
        cwd = os.path.realpath(pol["cwd"])
        ctx["stage"] = pol.get("stage", "")
    except Exception:
        deny("安全策略文件无效", ctx)

    if tool in READ_TOOLS:
        if tool == "Read":
            targets = [ti.get("file_path")]
        else:
            targets = [ti.get("path") or cwd]
            for key in ("pattern", "glob") if tool == "Glob" else ("glob",):
                if bad_pattern(ti.get(key)):
                    deny(f"{tool} 的匹配模式不能是绝对路径或包含 ..", ctx)
        for t in targets:
            if not t or not inside(resolve(t, cwd), read_roots + write_roots):
                deny(f"读取 {t} 超出允许范围", ctx)
        allow(ctx)

    if tool in WRITE_TOOLS:
        t = ti.get("file_path")
        if not t:
            deny("写入缺少路径", ctx)
        raw = os.path.expanduser(str(t))
        raw = raw if os.path.isabs(raw) else os.path.join(cwd, raw)
        if os.path.islink(raw):
            deny(f"不能通过符号链接写入 {t}", ctx)
        if not inside(resolve(t, cwd), write_roots):
            deny(f"写入 {t} 超出允许范围", ctx)
        allow(ctx)

    deny(f"工具 {tool or '(空)'} 不允许使用", ctx)


if __name__ == "__main__":
    main()
