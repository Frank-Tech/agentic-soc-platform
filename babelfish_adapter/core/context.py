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
    session_id: str            # UUID4 — used as X-Session-ID header
    trace_id: str              # client trace ID for Langfuse
    flow_id: str               # X-Flow-ID header for babelfish routing
    callbacks: list            # Langfuse CallbackHandler instances for the main flow
    trace_mapping: dict        # system_message_content → trace_id (for subflow tracing)
    subflow_handlers: dict     # system_message_content → CallbackHandler (populated at runtime)
    subflow_server_ids: dict   # system_message_content → msg_hash (for subflow session isolation)


babelfish_context: contextvars.ContextVar[Optional[BabelfishContextData]] = contextvars.ContextVar(
    "babelfish_context", default=None
)


# ── Subflow Helpers ───────────────────────────────────────────────────────────
# These functions are used by sub-agents to get their own Langfuse trace and
# session_id. The trace_mapping and subflow_server_ids are populated by the
# testing platform (lexus-test) and passed through the adapter's run().

def get_subflow_server_context(system_message_content: str) -> dict | None:
    """Derive a unique session_id for a subflow based on its system prompt.

    Returns {"session_id": str} if a mapping exists, None otherwise.
    The derived session_id ensures each subflow gets its own server-side trace.
    """
    import uuid as _uuid
    ctx = babelfish_context.get()
    if not ctx:
        return None
    server_ids = ctx.get("subflow_server_ids", {})
    sf_key = server_ids.get(system_message_content)
    if not sf_key:
        return None
    sf_session_id = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, f"{ctx['session_id']}-{sf_key}"))
    return {"session_id": sf_session_id}


def get_subflow_callbacks(system_message_content: str) -> list:
    """Create Langfuse callbacks for a subflow, keyed by its system prompt content.

    The trace_mapping (system_message_content → trace_id) is provided by lexus-test
    so each subflow gets a separate Langfuse trace.
    """
    ctx = babelfish_context.get()
    if not ctx:
        return []
    trace_id = ctx.get("trace_mapping", {}).get(system_message_content)
    if not trace_id:
        return []
    pub = os.environ.get("CLIENT_LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("CLIENT_LANGFUSE_SECRET_KEY")
    host = os.environ.get("CLIENT_LANGFUSE_HOST")
    if not (pub and sec and host):
        return []
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        Langfuse(public_key=pub, secret_key=sec, base_url=host)
        handler = CallbackHandler(public_key=pub, trace_context={"trace_id": trace_id})
        subflow_handlers = ctx.get("subflow_handlers", {})
        subflow_handlers[system_message_content] = handler
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

    Handles:
    1. Creating Langfuse callbacks for this subflow's trace
    2. Overriding session_id so this subflow gets its own server-side trace
    3. Cleaning up (resetting context, flushing callbacks) on exit

    Yields the list of callbacks to pass to RunnableConfig.
    """
    callbacks = get_subflow_callbacks(system_message_content)
    token = None

    sf_ctx = get_subflow_server_context(system_message_content)
    if sf_ctx:
        parent_ctx = babelfish_context.get()
        if parent_ctx:
            token = babelfish_context.set({**parent_ctx, "session_id": sf_ctx["session_id"]})

    try:
        yield callbacks
    finally:
        if token is not None:
            try:
                babelfish_context.reset(token)
            except ValueError:
                pass
        flush_callbacks(callbacks)
