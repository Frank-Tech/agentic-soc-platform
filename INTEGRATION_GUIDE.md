# Babelfish Adapter — Integration Guide

How to make any LangGraph-based project testable by **lexus-test** via the **babelfish** proxy.

This guide uses `agentic-soc-platform` as the reference implementation.

---

## What Is This?

**lexus-test** is a testing platform that runs agentic flows in pairs:
- **baseline** — direct LLM calls (e.g., OpenAI API)
- **babelfish** — proxied through babelfish for deterministic routing

It measures cost, latency, and token savings between the two modes.

Your project integrates by exposing a **babelfish adapter** — a Python module with 3 functions that lexus-test calls.

---

## Directory Structure

```
your_project/
  babelfish_adapter/
    __init__.py              # triggers bootstrap, re-exports contract functions
    core/                    # BABELFISH LAYER — generic, copy as-is
      __init__.py
      context.py             # ContextVar + subflow helpers + subflow_context()
      adapter.py             # YOUR implementation of run/list_payloads/list_flow_groups
    project/                 # PROJECT LAYER — your project's stubs & patches
      __init__.py
      bootstrap.py           # stub external deps that can't run during testing
```

### `core/` — Babelfish Protocol

- **`context.py`** — Copy this file unchanged. It provides:
  - `babelfish_context` ContextVar — carries mode/session_id/flow_id
  - `subflow_context()` context manager — for sub-agents that need their own trace
  - Helper functions for Langfuse callback management

- **`adapter.py`** — Write your own. Implements the 3 contract functions (see below).

### `project/` — Your Project's Baggage

- **`bootstrap.py`** — Stubs/patches for external dependencies your project uses.
  Each project is different. Examples from ASP:
  - Django cache stub (ASP uses django.core.cache)
  - SIRP/nocoly monkey-patch (commercial API, can't dockerize)
  - CONFIG module injection (so PLUGIN imports don't crash without real configs)
  - AlienVaultOTX stub (avoid hitting real threat intel API)

---

## The Contract

Your adapter must expose exactly 3 functions:

```python
async def run(
    *,
    mode: str,                              # "baseline" | "babelfish"
    session_id: str,                        # UUID4 — use as X-Session-ID header
    trace_id: str,                          # client trace ID for Langfuse
    flow_id: str,                           # X-Flow-ID header for babelfish routing
    payload_name: str,                      # one of the strings from list_payloads()
    trace_mapping: dict | None = None,      # system_message_content → trace_id (subflows)
    subflow_server_ids: dict | None = None, # system_message_content → hash (subflow sessions)
) -> AsyncGenerator[dict, None]:
    """Yields LangGraph-style {node_name: {"messages": [...]}} steps.
    
    At the end, yield a __trace_metadata__ dict:
    {"__trace_metadata__": {"client_trace_id": ..., "server_trace_id": ..., "subflow_trace_ids": {...}}}
    """

def list_payloads() -> list[str]:
    """Return all testable payload names. Format: 'entry_id:payload_name'.
    Called once at registration time."""

def list_flow_groups() -> list[dict]:
    """Return flow/subflow metadata for trace mapping.
    Each entry: {"entry_id": str, "flow": {"name": str, "system_message": str},
                 "subflows": [{"name": str, "system_message": str}, ...]}"""
```

---

## Step-by-Step: Integrating a New Project

### 1. Copy `core/context.py`

Copy `babelfish_adapter/core/context.py` into your project unchanged.

### 2. Write `core/adapter.py`

Implement the 3 contract functions. See the ASP implementation for a full example. Key sections:
- **Entries** — map entry_id strings to your runnable classes
- **Payloads** — define available test inputs
- **Flow Groups** — describe flow/subflow relationships
- **Input Builders** — convert payloads to your runnable's expected input
- **run()** — set babelfish_context, run your flow, yield steps

### 3. Write `project/bootstrap.py`

Stub out any external dependencies that can't run during testing.
If your project has no external deps, this file can be empty.

### 4. Hook into your LLM factory (~15 lines)

Your LLM factory (wherever you create ChatOpenAI/ChatOllama instances) needs to check `babelfish_context`:

```python
try:
    from babelfish_adapter.core.context import babelfish_context as _babelfish_context
except Exception:
    _babelfish_context = None

# In your get_model() or similar:
ctx = _babelfish_context.get() if _babelfish_context is not None else None
if ctx is not None:
    params["model"] = os.environ.get("ASP_ADAPTER_MODEL", "gpt-4o")
    params["api_key"] = os.environ["OPENAI_API_KEY"]
    if ctx.get("mode") == "babelfish":
        params["base_url"] = os.environ["OPENAI_BASE_URL"]
        params["default_headers"] = {
            "X-Session-ID": ctx["session_id"],
            "X-Flow-ID": ctx["flow_id"],
            "X-Api-Key": os.environ["NEXUS_API_KEY"],
            "X-Auto-Approve": "true",
        }
    else:  # baseline
        params["base_url"] = "https://api.openai.com/v1"
    return ChatOpenAI(**params)
```

> **CRITICAL: Do NOT cache LLM client instances across invocations.**
>
> `get_model()` bakes `X-Session-ID` and other headers into the `ChatOpenAI`
> instance at creation time. If you cache the client (e.g., `self._llm = get_model()`
> in `__init__`), all subsequent invocations reuse stale headers from the first call.
>
> **Wrong** — cached in `__init__`, headers frozen on first use:
> ```python
> def __init__(self):
>     self._llm = LLMAPI().get_model(tag=["fast"])  # STALE after first run
> ```
>
> **Right** — recreated per invocation, picks up current context:
> ```python
> def agent_node(state):
>     llm = LLMAPI().get_model(tag=["fast"])  # fresh headers every time
> ```

### 5. Hook into sub-agents (if any, ~5 lines each)

If your flow has sub-agents that should get separate traces:

```python
from contextlib import nullcontext

try:
    from babelfish_adapter.core.context import subflow_context as _subflow_context
except ImportError:
    _subflow_context = None

# In your sub-agent's query method:
ctx_mgr = _subflow_context(system_prompt_content) if _subflow_context else nullcontext([])
with ctx_mgr as sf_cbs:
    config = RunnableConfig(configurable={"thread_id": tid}, callbacks=sf_cbs)
    result = self.graph.invoke(state, config)
```

### 6. Environment variables

Add to your `.env`:
```
NEXUS_API_KEY=<from lexus-test>
OPENAI_API_KEY=<from lexus-test>
OPENAI_BASE_URL=https://babel-fish.tai42.nexus/openai/v1
CLIENT_LANGFUSE_PUBLIC_KEY=<from lexus-test>
CLIENT_LANGFUSE_SECRET_KEY=<from lexus-test>
CLIENT_LANGFUSE_HOST=<from lexus-test>
ASP_ADAPTER_MODEL=gpt-4o
```

### 7. Register with lexus-test

```
POST /api/flows/register-external
{
  "name": "your-project-name",
  "import_path": "babelfish_adapter:run",
  "description": "...",
  "execution_timeout_seconds": 300
}
```

lexus-test will call `list_payloads()` and `list_flow_groups()` automatically.

---

## Change Classification (agentic-soc-platform)

### Bug fixes (project-specific, found during integration testing)

| File | Fix |
|------|-----|
| `PLAYBOOKS/CASE/L3_SOC_Analyst_Agent_With_Tools.py` | Missing self-loop edge (NODE_ANALYZE) |
| `PLAYBOOKS/CASE/Threat_Hunting_Agent.py` | Analyst not prepending system message on loop-back |
| `PLAYBOOKS/CASE/Threat_Hunting_Agent.py` | Structured output parse failure |
| `PLUGINS/SIRP/sirpmodel.py` | Missing EXPLOITATION enum value |
| `AGENTS/agent_siem.py` | Stale LLM singleton, thread_id collision |
| `AGENTS/agent_threat_intelligence.py` | Thread_id collision |

### Integration changes (babelfish adapter)

| File | What |
|------|------|
| `babelfish_adapter/` | Entire adapter package |
| `PLUGINS/LLM/llmapi.py` | ~15 lines: ContextVar check in get_model() |
| `AGENTS/agent_siem.py` | ~5 lines: subflow_context() call |
| `AGENTS/agent_threat_intelligence.py` | ~5 lines: subflow_context() call |
| `.gitignore` | Added `**/CONFIG.py` |
