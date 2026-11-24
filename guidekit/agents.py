"""Locked-down agent runs (writing and reviewing chapters).

Each run is a headless `claude -p` with only Read/Glob/Grep/Write/Edit, no MCP servers, a scrubbed environment and a
PreToolUse guard hook (guard_hook.py) that enforces per-run read and write roots and fails closed. The agent never
runs commands or touches the network: checking is done by the harness after the run, and failures are sent back
for a fix round. Adapted from research-kb's agent runner.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TOOLS = "Read,Glob,Grep,Write,Edit"
HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
STATE = Path.home() / ".guidekit"
CLAUDE = shutil.which("claude") or "/opt/homebrew/bin/claude"
MODELS = {"opus": "opus", "sonnet": "sonnet", "haiku": "haiku"}


def _settings() -> Path:
    STATE.mkdir(exist_ok=True)
    s = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": f"{sys.executable} -I {HERE / 'guard_hook.py'}", "timeout": 20}]}]},
         "permissions": {"deny": ["Bash", "WebFetch", "WebSearch", "NotebookEdit", "Agent", "Task"]},
         "cleanupPeriodDays": 30}
    p = STATE / "settings.generated.json"
    text = json.dumps(s, indent=2)
    if not p.exists() or p.read_text() != text:
        p.write_text(text)
    return p


def _tool_results_dir(cwd: Path) -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def _policy(stage: str, cwd: Path, read_roots: list[Path], write_roots: list[Path]) -> Path:
    pol = {"stage": stage, "cwd": str(cwd),
           "read_roots": [str(p) for p in [*read_roots, _tool_results_dir(cwd)]],
           "write_roots": [str(p) for p in write_roots]}
    p = cwd / ".gk_policy.json"
    if p.exists():
        os.chmod(p, 0o644)
    p.write_text(json.dumps(pol, indent=2))
    os.chmod(p, 0o444)
    return p


def run(stage: str, prompt: str, cwd: Path, read_roots: list[Path], write_roots: list[Path],
        model: str = "opus", timeout_min: float = 60) -> dict:
    """One headless run. Returns {ok, result, turns, cost_usd, elapsed_s, exit}."""
    cwd.mkdir(parents=True, exist_ok=True)
    for w in write_roots:
        w.mkdir(parents=True, exist_ok=True)
    policy = _policy(stage, cwd, read_roots, write_roots)
    system = (TEMPLATES / "security.md").read_text()
    cmd = [CLAUDE, "--restricted", "--strict-mcp-config", "--tools", TOOLS, "--settings", str(_settings()),
           "--model", MODELS.get(model, model), "--append-system-prompt", system]
    added = set()
    for d in [*read_roots, *write_roots]:     # Claude Code itself only lets an agent touch its cwd and --add-dir folders
        r = d.resolve()
        if r != cwd.resolve() and not r.is_relative_to(cwd.resolve()) and r not in added:
            added.add(r)
            cmd += ["--add-dir", str(d)]
    cmd += ["-p", prompt, "--allowedTools", TOOLS, "--permission-mode", "dontAsk",
            "--no-session-persistence", "--output-format", "json"]
    env = {"HOME": str(Path.home()), "USER": os.environ.get("USER", ""), "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
           "LANG": "en_US.UTF-8", "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "GK_POLICY_FILE": str(policy)}
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_min * 60,
                           stdin=subprocess.DEVNULL)
        out, err, code = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        out, err, code = (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout", -1
    (cwd / f"{stage}.stdout.json").write_text(out or "")
    if err:
        (cwd / f"{stage}.stderr.txt").write_text(err)
    res = {"ok": False, "elapsed_s": round(time.time() - t0), "exit": code}
    try:
        d = json.loads(out)
        res.update(ok=(code == 0 and not d.get("is_error")), result=d.get("result", ""), turns=d.get("num_turns"),
                   cost_usd=d.get("total_cost_usd"), denials=len(d.get("permission_denials") or []))
    except Exception:
        res["result"] = (err or out or "")[-2000:]
    return res
