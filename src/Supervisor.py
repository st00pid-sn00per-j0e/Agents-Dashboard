# #!/usr/bin/env python3
# """
# NIZAMI CLI — Agentic AI Supervisor for browser-use agents.

# Architecture:
# Ollama Cloud (gpt-oss:120b-cloud) -> planning/merging
# G4F/browser-use agents -> real browser execution
# SQLite -> session logs
# Kuzu -> graph memory
# """

# import asyncio
# import json
# import os
# import re
# import sqlite3
# import sys
# import time
# from datetime import datetime
# from pathlib import Path
# from typing import Dict, List

# import dotenv
# from ollama import AsyncClient, ResponseError

# try:
#     import kuzu
# except ImportError:
#     kuzu = None

# from rich.console import Console
# from rich.panel import Panel
# from rich.text import Text
# from rich.live import Live
# from rich.spinner import Spinner
# from rich.table import Table
# try:
#     import pyfiglet
# except ImportError:
#     pyfiglet = None

# # `Supervisor.py` lives in `src/`, whereas agent sandboxes live at the
# # repository root.  Resolving paths from this file's directory therefore made
# # discovery look for `src/Sandboxes`, which does not exist in a normal checkout.
# SOURCE_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT = SOURCE_DIR.parent
# ROOT = PROJECT_ROOT
# # Support both common layouts: project-root `.env` for normal deployments and
# # `src/.env` for the existing project layout.  The project-level file wins
# # when both are present.
# ENV_FILE = next(
#     (path for path in (PROJECT_ROOT / ".env", SOURCE_DIR / ".env") if path.is_file()),
#     PROJECT_ROOT / ".env",
# )
# SANDBOX_BASE = ROOT / "Sandboxes"
# AGENT_SCRIPT = "Agent_1.py"
# OLLAMA_HOST = "https://ollama.com"
# MODEL_NAME = "gpt-oss:120b-cloud"
# SQLITE_DB = ROOT / "supervisor.db"
# KUZU_DB = ROOT / "kuzu_db"

# # Ollama request tuning
# OLLAMA_TIMEOUT_SECS = 60
# OLLAMA_MAX_RETRIES = 3
# OLLAMA_RETRY_BACKOFF = 2.0

# GREEN = "#00E6A6"  # matches Nizami's BoxTech accent green
# console = Console()

# dotenv.load_dotenv(ENV_FILE)
# OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
# OLLAMA_HOST = os.getenv("OLLAMA_HOST", OLLAMA_HOST)
# MODEL_NAME = os.getenv("OLLAMA_MODEL", MODEL_NAME)
# SANDBOX_BASE = Path(os.getenv("AGENT_SANDBOX_BASE", str(SANDBOX_BASE))).expanduser()

# # Allow the CLI to start and enumerate local agents without cloud credentials.
# # The key is required only when the user submits a task that needs planning or
# # result merging.
# ollama_client = (
#     AsyncClient(
#         host=OLLAMA_HOST,
#         headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"},
#         timeout=OLLAMA_TIMEOUT_SECS,
#     )
#     if OLLAMA_API_KEY
#     else None
# )


# # --------------------------------------------------------------------------
# # Banner / animation
# # --------------------------------------------------------------------------
# def print_banner():
#     """Render the NIZAMI CLI ASCII banner in a green hue, with a short animation."""
#     title = "NIZAMI CLI"
#     subtitle = "A G E N T I C   A I"

#     if pyfiglet:
#         ascii_art = pyfiglet.figlet_format(title, font="slant")
#     else:
#         ascii_art = title  # graceful fallback if pyfiglet missing

#     frames = []
#     lines = ascii_art.rstrip("\n").split("\n")
#     max_len = max(len(l) for l in lines) if lines else 0

#     # simple "reveal" animation: sweep the art in column by column
#     steps = max(6, max_len // 6)
#     for step in range(1, steps + 1):
#         cutoff = int(max_len * step / steps)
#         frame_lines = [l[:cutoff] for l in lines]
#         frames.append("\n".join(frame_lines))

#     # pad every frame to the full art width so the panel border doesn't
#     # resize/shrink-wrap mid-animation (that's what caused the clipped box)
#     with Live(console=console, refresh_per_second=30, transient=True) as live:
#         for frame in frames:
#             padded = "\n".join(l.ljust(max_len) for l in frame.split("\n"))
#             text = Text(padded, style=f"bold {GREEN}")
#             live.update(Panel(text, border_style=GREEN, expand=False))
#             time.sleep(0.02)

#     final_text = Text(ascii_art, style=f"bold {GREEN}")
#     console.print(Panel(
#         final_text,
#         subtitle=f"[{GREEN}]{subtitle}[/{GREEN}]",
#         border_style=GREEN,
#         expand=False,
#     ))
#     # Keep startup output ASCII-only so Rich also works in legacy Windows
#     # terminals whose output encoding is cp1252.
#     console.print(f"[{GREEN}]* Ollama Cloud ({MODEL_NAME}) - browser-use agents - SQLite - Kuzu graph memory[/{GREEN}]\n")


# # --------------------------------------------------------------------------
# # Storage init
# # --------------------------------------------------------------------------
# def init_sqlite():
#     con = sqlite3.connect(SQLITE_DB)
#     cur = con.cursor()
#     cur.executescript("""
#     CREATE TABLE IF NOT EXISTS sessions(
#         id INTEGER PRIMARY KEY,
#         uuid TEXT,
#         task TEXT,
#         output TEXT,
#         status TEXT,
#         created TEXT
#     );
#     CREATE TABLE IF NOT EXISTS agents(
#         id INTEGER PRIMARY KEY,
#         session_id INTEGER,
#         name TEXT,
#         subtask TEXT,
#         response TEXT,
#         created TEXT
#     );
#     """)
#     con.commit()
#     con.close()


# def init_kuzu():
#     if not kuzu:
#         return None
#     db = kuzu.Database(KUZU_DB)
#     conn = kuzu.Connection(db)
#     conn.execute("CREATE NODE TABLE IF NOT EXISTS Session(uuid STRING PRIMARY KEY, task STRING)")
#     conn.execute("CREATE NODE TABLE IF NOT EXISTS Agent(name STRING PRIMARY KEY)")
#     conn.execute("CREATE NODE TABLE IF NOT EXISTS Task(name STRING PRIMARY KEY)")
#     conn.execute("CREATE REL TABLE IF NOT EXISTS ASSIGNED(FROM Task TO Agent)")
#     return db


# # --------------------------------------------------------------------------
# # Ollama Cloud client
# # --------------------------------------------------------------------------
# async def ollama(prompt: str, system: str = "") -> str:
#     """
#     Call Ollama Cloud via the official `ollama` Python library (AsyncClient).

#     - client-level timeout is set on ollama_client itself
#     - retries with backoff on transient failures (connection errors, 429/5xx)
#     - validates response shape instead of blindly trusting it
#     """
#     if ollama_client is None:
#         raise RuntimeError(
#             f"Missing OLLAMA_API_KEY. Add it to {ENV_FILE} or set it in the environment."
#         )

#     messages = []
#     if system:
#         messages.append({"role": "system", "content": system})
#     messages.append({"role": "user", "content": prompt})

#     last_err = None
#     for attempt in range(1, OLLAMA_MAX_RETRIES + 1):
#         try:
#             resp = await ollama_client.chat(
#                 model=MODEL_NAME,
#                 messages=messages,
#                 options={"temperature": 0.2},
#             )

#             content = None
#             if hasattr(resp, "message") and resp.message is not None:
#                 content = resp.message.content
#             elif isinstance(resp, dict):
#                 content = (resp.get("message") or {}).get("content")

#             if content is None:
#                 raise RuntimeError(f"Ollama response missing message content: {resp}")

#             return content

#         except ResponseError as e:
#             # ResponseError carries an HTTP status_code; retry on 429/5xx, fail fast otherwise
#             status = getattr(e, "status_code", None)
#             last_err = e
#             if status is not None and status != 429 and not (500 <= status < 600):
#                 raise
#         except Exception as e:
#             last_err = e

#         if attempt < OLLAMA_MAX_RETRIES:
#             wait = OLLAMA_RETRY_BACKOFF * attempt
#             console.print(f"[yellow]Ollama call failed (attempt {attempt}/{OLLAMA_MAX_RETRIES}): {last_err}. Retrying in {wait:.1f}s...[/yellow]")
#             await asyncio.sleep(wait)

#     raise RuntimeError(f"Ollama call failed after {OLLAMA_MAX_RETRIES} attempts: {last_err}")


# def discover_agents() -> Dict[str, Path]:
#     """Return direct sandbox children that contain an agent entrypoint.

#     `AGENT_SANDBOX_BASE` can override the default `<project>/Sandboxes` path
#     for packaged or multi-repository deployments.
#     """
#     result: Dict[str, Path] = {}
#     sandbox_base = SANDBOX_BASE.resolve()
#     if not sandbox_base.is_dir():
#         return result

#     for path in sorted(sandbox_base.iterdir(), key=lambda item: item.name.casefold()):
#         entrypoint = path / AGENT_SCRIPT
#         if path.is_dir() and entrypoint.is_file():
#             result[path.name] = path.resolve()
#     return result


# async def run_agent(name: str, folder: Path, task: str) -> str:
#     env = os.environ.copy()
#     env["AGENT_TASK"] = task
#     env["BROWSER_PROFILE"] = str(ROOT / "profiles" / name)

#     proc = await asyncio.create_subprocess_exec(
#         sys.executable,
#         str(folder / AGENT_SCRIPT),
#         cwd=str(folder),
#         env=env,
#         stdout=asyncio.subprocess.PIPE,
#         stderr=asyncio.subprocess.PIPE,
#     )

#     try:
#         out, err = await asyncio.wait_for(proc.communicate(), timeout=900)
#     except asyncio.TimeoutError:
#         proc.kill()
#         await proc.communicate()
#         raise RuntimeError(f"{name} timeout")

#     text = out.decode(errors="replace")
#     if not text:
#         text = err.decode(errors="replace")
#     return text


# async def decompose(task: str, names: List[str]) -> Dict[str, str]:
#     if ollama_client is None:
#         # Keep local execution available when cloud planning is not configured.
#         # Every discovered agent receives the full task in this mode.
#         return {name: task for name in names}

#     prompt = f"""
# Task: {task}
# Agents: {names}
# Return ONLY JSON mapping agent names to subtasks.
# """
#     raw = await ollama(prompt, "Return valid JSON only")
#     try:
#         return json.loads(raw)
#     except json.JSONDecodeError:
#         m = re.search(r"\{.*\}", raw, re.S)
#         if m:
#             try:
#                 return json.loads(m.group())
#             except json.JSONDecodeError:
#                 pass
#         # last-resort fallback: give every agent the full task
#         return {n: task for n in names}


# async def merge(task: str, outputs: Dict[str, str]) -> str:
#     if ollama_client is None:
#         sections = [f"[{name}]\n{output}" for name, output in outputs.items()]
#         return "\n\n".join(sections)

#     return await ollama(
#         f"Task:{task}\nOutputs:{json.dumps(outputs)}",
#         "Merge agent results into final answer",
#     )


# def store(task: str, merged: str, outputs: Dict[str, str]) -> str:
#     uid = str(time.time_ns())
#     con = sqlite3.connect(SQLITE_DB)
#     cur = con.cursor()
#     cur.execute(
#         "INSERT INTO sessions(uuid,task,output,status,created) VALUES(?,?,?,?,?)",
#         (uid, task, merged, "completed", datetime.now().isoformat()),
#     )
#     sid = cur.lastrowid
#     for n, r in outputs.items():
#         cur.execute(
#             "INSERT INTO agents(session_id,name,subtask,response,created) VALUES(?,?,?,?,?)",
#             (sid, n, "", r, datetime.now().isoformat()),
#         )
#     con.commit()
#     con.close()
#     return uid


# async def main():
#     print_banner()

#     init_sqlite()
#     init_kuzu()

#     agents = discover_agents()
#     if ollama_client is None:
#         console.print(
#             "[yellow]OLLAMA_API_KEY is not configured; using direct agent dispatch "
#             "and unmerged local results.[/yellow]"
#         )
#     table = Table(border_style=GREEN, show_header=True, header_style=f"bold {GREEN}")
#     table.add_column("Agent")
#     table.add_column("Path")
#     for n, p in agents.items():
#         table.add_row(n, str(p))
#     if agents:
#         console.print(table)
#     else:
#         console.print(f"[{GREEN}]No agents discovered under[/{GREEN}] {SANDBOX_BASE}")

#     while True:
#         task = console.input(f"[bold {GREEN}]Task>[/bold {GREEN}] ").strip()
#         if task.lower() in ("exit", "quit"):
#             break
#         if not task:
#             continue

#         if not agents:
#             console.print(
#                 f"[red]No agents discovered under[/red] {SANDBOX_BASE}. "
#                 f"Add a subfolder containing {AGENT_SCRIPT} before running a task.\n"
#             )
#             continue

#         try:
#             with console.status(f"[{GREEN}]Planning with Ollama Cloud...[/{GREEN}]", spinner="dots"):
#                 plan = await decompose(task, list(agents))
#         except Exception as e:
#             console.print(f"[red]Planning failed:[/red] {e}")
#             continue

#         jobs = []
#         names = []
#         for n, t in plan.items():
#             if n in agents:
#                 jobs.append(run_agent(n, agents[n], t))
#                 names.append(n)

#         if not jobs:
#             console.print(f"[red]No matching agents for plan:[/red] {plan}")
#             continue

#         with console.status(f"[{GREEN}]Running {len(jobs)} agent(s)...[/{GREEN}]", spinner="dots"):
#             results = await asyncio.gather(*jobs, return_exceptions=True)

#         outputs = {
#             n: ("ERROR " + str(r) if isinstance(r, Exception) else r)
#             for n, r in zip(names, results)
#         }

#         try:
#             with console.status(f"[{GREEN}]Merging results...[/{GREEN}]", spinner="dots"):
#                 final = await merge(task, outputs)
#         except Exception as e:
#             console.print(f"[red]Merge failed:[/red] {e}")
#             continue

#         uid = store(task, final, outputs)

#         console.print(Panel(final, title="FINAL RESULT", border_style=GREEN))
#         console.print(f"[{GREEN}]SESSION[/{GREEN}] {uid}\n")


# if __name__ == "__main__":
#     asyncio.run(main())


#!/usr/bin/env python3
"""
NIZAMI CLI — Agentic Reasoning Supervisor.

This process is the "brain": it reads a task, decides whether it can answer
it directly or whether it needs to hand work off to sandboxed agents, and if
so, decides HOW to hand it off — one shared project all agents collaborate
on, or separate independent subtasks, one per agent.

Design constraints (intentional):
- The supervisor NEVER opens, reads, or edits any file inside a sandbox.
  It only (a) checks that `Sandboxes/<name>/Agent_1.py` exists, and
  (b) launches it as a subprocess with a task string in an env var.
  What the agent script contains, and what it does with the task, is opaque
  to the supervisor by design — this is terminal-level access, not
  file-level access.
- Nothing about the underlying model provider, database, or graph store is
  surfaced anywhere in the CLI's visible output. The user sees "reasoning",
  "agents", and "results" — not implementation details.
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import dotenv
from ollama import AsyncClient, ResponseError

try:
    import kuzu
except ImportError:
    kuzu = None

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table

try:
    import pyfiglet
except ImportError:
    pyfiglet = None

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
# `Supervisor.py` lives in `src/`; sandboxes live at the repository root.
SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent
ROOT = PROJECT_ROOT

# project-root `.env` wins over `src/.env` when both exist
ENV_FILE = next(
    (p for p in (PROJECT_ROOT / ".env", SOURCE_DIR / ".env") if p.is_file()),
    PROJECT_ROOT / ".env",
)

SANDBOX_BASE = ROOT / "Sandboxes"
AGENT_SCRIPT = "Agent_1.py"

STATE_DB = ROOT / "supervisor.db"
GRAPH_DB = ROOT / "kuzu_db"

REASONING_TIMEOUT_SECS = 60
REASONING_MAX_RETRIES = 3
REASONING_RETRY_BACKOFF = 2.0

GREEN = "#00E6A6"  # matches Nizami's BoxTech accent green
console = Console()

dotenv.load_dotenv(ENV_FILE)
_API_KEY = os.getenv("OLLAMA_API_KEY")
_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud")
SANDBOX_BASE = Path(os.getenv("AGENT_SANDBOX_BASE", str(SANDBOX_BASE))).expanduser()

# The CLI still starts and lists agents without a configured reasoning
# backend; a key is only required once the user submits a task.
_client = (
    AsyncClient(host=_HOST, headers={"Authorization": f"Bearer {_API_KEY}"}, timeout=REASONING_TIMEOUT_SECS)
    if _API_KEY
    else None
)


# ----------------------------------------------------------------------------
# Banner
# ----------------------------------------------------------------------------
def print_banner():
    title = "NIZAMI CLI"
    subtitle = "A G E N T I C   A I"

    ascii_art = pyfiglet.figlet_format(title, font="slant") if pyfiglet else title
    lines = ascii_art.rstrip("\n").split("\n")
    max_len = max((len(l) for l in lines), default=0)

    steps = max(6, max_len // 6)
    frames = []
    for step in range(1, steps + 1):
        cutoff = int(max_len * step / steps)
        frames.append("\n".join(l[:cutoff] for l in lines))

    with Live(console=console, refresh_per_second=30, transient=True) as live:
        for frame in frames:
            padded = "\n".join(l.ljust(max_len) for l in frame.split("\n"))
            live.update(Panel(Text(padded, style=f"bold {GREEN}"), border_style=GREEN, expand=False))
            time.sleep(0.02)

    console.print(Panel(
        Text(ascii_art, style=f"bold {GREEN}"),
        subtitle=f"[{GREEN}]{subtitle}[/{GREEN}]",
        border_style=GREEN,
        expand=False,
    ))
    console.print(f"[{GREEN}]* Reasoning engine online  ·  sandboxed agent execution ready[/{GREEN}]\n")


# ----------------------------------------------------------------------------
# Local storage
# ----------------------------------------------------------------------------
def init_state_db():
    con = sqlite3.connect(STATE_DB)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY,
        uuid TEXT,
        task TEXT,
        mode TEXT,
        distribution TEXT,
        output TEXT,
        status TEXT,
        created TEXT
    );
    CREATE TABLE IF NOT EXISTS agent_runs(
        id INTEGER PRIMARY KEY,
        session_id INTEGER,
        name TEXT,
        subtask TEXT,
        response TEXT,
        created TEXT
    );
    """)

    # Earlier releases created `sessions` without these dispatch metadata
    # columns. `CREATE TABLE IF NOT EXISTS` does not evolve an existing table,
    # so migrate it before `store_session` writes the new record shape.
    session_columns = {
        row[1] for row in cur.execute("PRAGMA table_info(sessions)")
    }
    for column in ("mode", "distribution"):
        if column not in session_columns:
            cur.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")

    con.commit()
    con.close()


def init_graph_db():
    if not kuzu:
        return None
    db = kuzu.Database(GRAPH_DB)
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Session(uuid STRING PRIMARY KEY, task STRING)")
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Agent(name STRING PRIMARY KEY)")
    conn.execute("CREATE NODE TABLE IF NOT EXISTS Task(name STRING PRIMARY KEY)")
    conn.execute("CREATE REL TABLE IF NOT EXISTS ASSIGNED(FROM Task TO Agent)")
    return db


def store_session(task: str, mode: str, distribution: Optional[str], merged: str, outputs: Dict[str, str]) -> str:
    uid = str(time.time_ns())
    con = sqlite3.connect(STATE_DB)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sessions(uuid,task,mode,distribution,output,status,created) VALUES(?,?,?,?,?,?,?)",
        (uid, task, mode, distribution or "", merged, "completed", datetime.now().isoformat()),
    )
    sid = cur.lastrowid
    for name, resp in outputs.items():
        cur.execute(
            "INSERT INTO agent_runs(session_id,name,subtask,response,created) VALUES(?,?,?,?,?)",
            (sid, name, "", resp, datetime.now().isoformat()),
        )
    con.commit()
    con.close()
    return uid


# ----------------------------------------------------------------------------
# Reasoning engine call (provider details never leak past this function)
# ----------------------------------------------------------------------------
async def think(prompt: str, system: str = "") -> str:
    if _client is None:
        raise RuntimeError(f"Reasoning engine is not configured. Add credentials to {ENV_FILE}.")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_err = None
    for attempt in range(1, REASONING_MAX_RETRIES + 1):
        try:
            resp = await _client.chat(model=_MODEL, messages=messages, options={"temperature": 0.2})
            content = None
            if hasattr(resp, "message") and resp.message is not None:
                content = resp.message.content
            elif isinstance(resp, dict):
                content = (resp.get("message") or {}).get("content")
            if content is None:
                raise RuntimeError(f"Reasoning engine returned no content: {resp}")
            return content
        except ResponseError as e:
            status = getattr(e, "status_code", None)
            last_err = e
            if status is not None and status != 429 and not (500 <= status < 600):
                raise
        except Exception as e:
            last_err = e

        if attempt < REASONING_MAX_RETRIES:
            wait = REASONING_RETRY_BACKOFF * attempt
            console.print(f"[yellow]Reasoning call failed (attempt {attempt}/{REASONING_MAX_RETRIES}): {last_err}. Retrying in {wait:.1f}s...[/yellow]")
            await asyncio.sleep(wait)

    raise RuntimeError(f"Reasoning engine call failed after {REASONING_MAX_RETRIES} attempts: {last_err}")


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    raise ValueError(f"Could not parse JSON from reasoning output: {raw[:300]}")


# ----------------------------------------------------------------------------
# Sandbox discovery / execution — folder + entrypoint existence only.
# The supervisor never opens agent source files.
# ----------------------------------------------------------------------------
def discover_agents() -> Dict[str, Path]:
    result: Dict[str, Path] = {}
    base = SANDBOX_BASE.resolve()
    if not base.is_dir():
        return result
    for path in sorted(base.iterdir(), key=lambda p: p.name.casefold()):
        entry = path / AGENT_SCRIPT
        if path.is_dir() and entry.is_file():
            result[path.name] = path.resolve()
    return result


async def run_agent(name: str, folder: Path, task: str) -> str:
    env = os.environ.copy()
    env["AGENT_TASK"] = task
    env["BROWSER_PROFILE"] = str(ROOT / "profiles" / name)

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(folder / AGENT_SCRIPT),
        cwd=str(folder),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=900)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError(f"{name} timeout")

    text = out.decode(errors="replace")
    if not text:
        text = err.decode(errors="replace")
    return text


# ----------------------------------------------------------------------------
# The actual reasoning step: understand the WHOLE request at once, and
# decide (a) direct answer vs dispatch, (b) if dispatch, shared project vs
# split independent tasks, (c) which agents, and (d) what each gets told.
# ----------------------------------------------------------------------------
ROUTING_SYSTEM_PROMPT = """You are the reasoning core of an agent supervisor.
You receive one user request and a list of available sandboxed worker agents
(only their names — you do not know their internal code).

Decide ONE of two modes:
- "direct": you can fully answer the request yourself, in text, with no
  need for any agent to take an action (browsing, scraping, executing
  something in an environment, interacting with external systems, etc).
  Use this for questions, explanations, brainstorming, writing, math,
  anything answerable from reasoning/knowledge alone.
- "dispatch": the request requires one or more agents to actually do
  something (browse the web, operate on files/systems inside their
  sandbox, run a multi-step task, gather live information, etc).

If mode is "dispatch", also decide the distribution:
- "shared": the user wants ALL agents collaborating toward ONE outcome /
  one project (e.g. "have the team build me a report", "get this done
  using whatever agents are available"). In this case every selected
  agent should receive an appropriately-scoped restatement of the SAME
  overall goal (you may tailor phrasing per agent, but the goal is one
  project).
- "split": the user wants DIFFERENT, independent tasks handled separately
  (e.g. "agent A do X, agent B do Y", "check three different things",
  or a request that naturally decomposes into unrelated subtasks). In
  this case decompose the request into distinct subtasks, one per agent,
  and only select the agents actually needed.

Only select agents that are relevant — do not force every agent into a plan
that doesn't need them.

Respond with ONLY a JSON object, no prose, no markdown fences, matching
exactly one of these shapes:

For direct mode:
{"mode": "direct", "answer": "<full answer text>"}

For dispatch mode:
{"mode": "dispatch", "distribution": "shared" | "split",
 "reasoning": "<one short sentence explaining the choice, shown to the user>",
 "plan": {"<agent_name>": "<task text for that agent>", ...}}

Never invent agent names that were not given to you.
"""


async def reason_about_task(task: str, agent_names: List[str]) -> dict:
    if not agent_names:
        # No agents exist at all — the only possible mode is direct.
        prompt = f"User request:\n{task}\n\nThere are no agents available. Answer directly."
        raw = await think(prompt, ROUTING_SYSTEM_PROMPT)
        try:
            parsed = _extract_json(raw)
            if parsed.get("mode") == "direct" and "answer" in parsed:
                return parsed
        except ValueError:
            pass
        return {"mode": "direct", "answer": raw}

    prompt = f"""User request:
{task}

Available agents: {agent_names}

Decide and respond with the JSON object described in your instructions."""
    raw = await think(prompt, ROUTING_SYSTEM_PROMPT)
    parsed = _extract_json(raw)

    if parsed.get("mode") not in ("direct", "dispatch"):
        raise ValueError(f"Reasoning output had invalid mode: {parsed}")

    if parsed["mode"] == "dispatch":
        plan = parsed.get("plan") or {}
        # keep only agents that actually exist
        parsed["plan"] = {n: t for n, t in plan.items() if n in agent_names}
        if not parsed["plan"]:
            raise ValueError(f"Reasoning produced no valid agent assignments: {parsed}")
        if parsed.get("distribution") not in ("shared", "split"):
            # default to split if the model forgot to specify
            parsed["distribution"] = "split"

    return parsed


async def merge_outputs(task: str, distribution: str, outputs: Dict[str, str]) -> str:
    style = (
        "The agents were all working on ONE shared project together — "
        "synthesize their outputs into a single coherent final result."
        if distribution == "shared"
        else "The agents each handled a separate, independent subtask — "
        "present their results clearly grouped by agent, then add a brief overall summary."
    )
    return await think(
        f"Original request:\n{task}\n\nAgent outputs:\n{json.dumps(outputs, indent=2)}",
        f"You are merging results from sandboxed agents. {style}",
    )


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
async def main():
    print_banner()
    init_state_db()
    init_graph_db()

    agents = discover_agents()

    if _client is None:
        console.print(f"[yellow]Reasoning engine is not configured. Add credentials to {ENV_FILE} before submitting tasks.[/yellow]")

    table = Table(border_style=GREEN, show_header=True, header_style=f"bold {GREEN}")
    table.add_column("Agent")
    table.add_column("Sandbox")
    for n, p in agents.items():
        table.add_row(n, str(p))
    if agents:
        console.print(table)
    else:
        console.print(f"[{GREEN}]No agents discovered under[/{GREEN}] {SANDBOX_BASE}")
    console.print()

    while True:
        task = console.input(f"[bold {GREEN}]Task>[/bold {GREEN}] ").strip()
        if task.lower() in ("exit", "quit"):
            break
        if not task:
            continue

        try:
            with console.status(f"[{GREEN}]Reasoning...[/{GREEN}]", spinner="dots"):
                decision = await reason_about_task(task, list(agents))
        except Exception as e:
            console.print(f"[red]Reasoning failed:[/red] {e}\n")
            continue

        # ---- Direct answer, no agents touched ----
        if decision["mode"] == "direct":
            answer = decision.get("answer", "").strip()
            store_session(task, "direct", None, answer, {})
            console.print(Panel(answer, title="RESULT", border_style=GREEN))
            console.print()
            continue

        # ---- Dispatch to agents ----
        distribution = decision["distribution"]
        plan = decision["plan"]
        reasoning_note = decision.get("reasoning", "")

        label = "one shared project" if distribution == "shared" else "separate independent tasks"
        note = f" — {reasoning_note}" if reasoning_note else ""
        console.print(f"[{GREEN}]Dispatching to {len(plan)} agent(s) as {label}{note}[/{GREEN}]")

        jobs = [run_agent(name, agents[name], subtask) for name, subtask in plan.items()]
        names = list(plan.keys())

        with console.status(f"[{GREEN}]Running {len(jobs)} agent(s)...[/{GREEN}]", spinner="dots"):
            results = await asyncio.gather(*jobs, return_exceptions=True)

        outputs = {
            n: ("ERROR " + str(r) if isinstance(r, Exception) else r)
            for n, r in zip(names, results)
        }

        try:
            with console.status(f"[{GREEN}]Merging results...[/{GREEN}]", spinner="dots"):
                final = await merge_outputs(task, distribution, outputs)
        except Exception as e:
            console.print(f"[red]Merge failed:[/red] {e}\n")
            continue

        uid = store_session(task, "dispatch", distribution, final, outputs)

        console.print(Panel(final, title="FINAL RESULT", border_style=GREEN))
        console.print(f"[{GREEN}]SESSION[/{GREEN}] {uid}\n")


if __name__ == "__main__":
    asyncio.run(main())
