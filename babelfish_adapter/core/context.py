# ═══════════════════════════════════════════════════════════════════════════════
# BABELFISH CONTEXT — Generic Protocol Layer
# ═══════════════════════════════════════════════════════════════════════════════
#
# This module is PROJECT-INDEPENDENT. Copy it as-is into any project that
# integrates with lexus-test via the babelfish proxy.
#
# It provides:
#   1. A ContextVar that carries babelfish session state (mode, session_id, etc.)
#   2. Helper functions for subflow tracing (Langfuse callbacks, session isolation)
#   3. A context manager (subflow_context) that sub-agents use to get proper
#      tracing with minimal boilerplate
#
# HOW IT WORKS:
#   - The adapter's run() sets babelfish_context before executing the flow
#   - The project's LLM factory reads babelfish_context to decide whether to
#     route LLM calls through babelfish (proxy) or directly to the provider
#   - Sub-agents use subflow_context() to get their own Langfuse trace and
#     session_id, enabling per-subflow trace separation
#
# CRITICAL — LLM CLIENT CACHING PITFALL:
#   The LLM factory bakes X-Session-ID and other headers into the ChatOpenAI
#   instance at creation time. LLM clients MUST be created fresh per invocation
#   (inside agent_node functions), NOT cached in __init__ or as class attributes.
#   Cached clients carry stale headers from the first invocation.
#
# ═══════════════════════════════════════════════════════════════════════════════

import contextvars
import os
from contextlib import contextmanager
from typing import Optional, TypedDict


# ── ContextVar Definition ─────────────────────────────────────────────────────

class BabelfishContextData(TypedDict):
    mode: str                  # "baseline" | "babelfish"
    session_id: str            # UUID4 — used as X-Session-ID header (overridden per subflow invocation)
    trace_id: str              # client trace ID for Langfuse (main flow)
    flow_id: str               # X-Flow-ID header for babelfish routing
    callbacks: list            # Langfuse CallbackHandler instances for the main flow
    subflow_server_ids: dict   # system_message_content → msg_hash (identifies tracked subflows)
    subflow_invocations: list  # accumulator: list[{msg_hash, client_trace_id, server_session_id}]


babelfish_context: contextvars.ContextVar[Optional[BabelfishContextData]] = contextvars.ContextVar(
    "babelfish_context", default=None
)


# ── Subflow Helpers ───────────────────────────────────────────────────────────
# These functions are used by subflow_context() below. The subflow_server_ids
# dict (system_message_content → msg_hash) is populated by lexus-test and
# passed through the adapter's run(); it identifies which system messages
# correspond to tracked subflows. Fresh IDs are generated per invocation so
# parallel calls (e.g. LangGraph Send fan-out) produce distinct traces.

def _is_tracked_subflow(system_message_content: str) -> str | None:
    """Return the msg_hash if this system message is a tracked subflow, else None."""
    ctx = babelfish_context.get()
    if not ctx:
        return None
    server_ids = ctx.get("subflow_server_ids", {})
    return server_ids.get(system_message_content)


def _build_subflow_callback(client_trace_id: str) -> list:
    """Build a fresh Langfuse CallbackHandler for a single subflow invocation."""
    pub = os.environ.get("CLIENT_LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("CLIENT_LANGFUSE_SECRET_KEY")
    host = os.environ.get("CLIENT_LANGFUSE_HOST")
    if not (pub and sec and host):
        return []
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        Langfuse(public_key=pub, secret_key=sec, base_url=host)
        handler = CallbackHandler(public_key=pub, trace_context={"trace_id": client_trace_id})
        return [handler]
    except Exception:
        return []


def flush_callbacks(callbacks: list) -> None:
    """Flush all Langfuse clients to ensure trace data is sent."""
    for cb in callbacks:
        if hasattr(cb, "_langfuse_client"):
            try:
                cb._langfuse_client.flush()
            except Exception:
                pass


# ── Subflow Context Manager ──────────────────────────────────────────────────
# Use this in sub-agents to set up tracing + session isolation in one call.
#
# Usage in a sub-agent:
#   with subflow_context(system_prompt_content) as callbacks:
#       config = RunnableConfig(configurable={"thread_id": tid}, callbacks=callbacks)
#       result = self.graph.invoke(state, config)

@contextmanager
def subflow_context(system_message_content: str):
    """Context manager for sub-agent babelfish integration.

    On every entry, generates fresh per-invocation IDs:
      - client_trace_id (uuid4) for a new Langfuse client trace
      - server_session_id (uuid4) sent as X-Session-ID so holy-grail creates
        a distinct server trace

    The invocation is recorded in ``ctx["subflow_invocations"]`` so the
    adapter can return the full list to lexus-test (which polls each trace
    and creates one run record per invocation).

    This is safe for parallel fan-out (LangGraph Send) because:
      - ContextVars are copied per asyncio task, so each task's session_id
        override is isolated
      - list.append() is atomic under the GIL
    """
    import uuid as _uuid

    parent_ctx = babelfish_context.get()
    if not parent_ctx:
        yield []
        return

    msg_hash = _is_tracked_subflow(system_message_content)
    if not msg_hash:
        # Not a tracked subflow — no callbacks, no session override.
        yield []
        return

    client_trace_id = str(_uuid.uuid4()).replace("-", "")
    server_session_id = str(_uuid.uuid4())

    parent_ctx["subflow_invocations"].append({
        "msg_hash": msg_hash,
        "client_trace_id": client_trace_id,
        "server_session_id": server_session_id,
    })

    callbacks = _build_subflow_callback(client_trace_id)
    token = babelfish_context.set({**parent_ctx, "session_id": server_session_id})
    try:
        yield callbacks
    finally:
        try:
            babelfish_context.reset(token)
        except ValueError:
            pass
        flush_callbacks(callbacks)
