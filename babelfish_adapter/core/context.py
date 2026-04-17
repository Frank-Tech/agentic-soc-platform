# ═══════════════════════════════════════════════════════════════════════════════
# BABELFISH CONTEXT — Generic Protocol Layer
# ═══════════════════════════════════════════════════════════════════════════════
#
# This module is PROJECT-INDEPENDENT. Copy it as-is into any project that
# integrates with lexus-test via the babelfish proxy.
#
# ─── Design: explicit session_id, no inheritance ────────────────────────────
#
# Every flow role (parent flow, every subflow) is responsible for minting its
# own fresh UUID4 ``session_id`` and passing it explicitly to the LLM factory
# (``LLMAPI.get_model(..., session_id=...)``).  There is NO implicit default,
# no ContextVar-based inheritance, and no parent-session override dance.  This
# makes the "forgot to wrap a concurrent Send fan-out" bug structurally
# impossible — every LLM call site must declare which session it belongs to,
# or the call refuses to build.
#
# ``babelfish_context`` still exists, but it only carries cross-cutting state
# that's invariant across all calls inside one adapter.run() invocation:
#   - mode           ("babelfish" | "baseline")
#   - flow_id        (X-Flow-ID header)
#   - subflow_server_ids  (which system messages belong to tracked subflows)
#   - subflow_invocations (accumulator for __trace_metadata__)
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
import uuid as _uuid
from typing import Optional, TypedDict

from langchain_core.callbacks import BaseCallbackHandler


class _CallbackIsolationHandler(BaseCallbackHandler):
    """No-op handler that prevents LangChain parent-callback inheritance.

    LangChain's ``CallbackManager.configure()`` treats ``callbacks=[]``
    (empty list) as falsy and falls through to the parent graph's ambient
    callback context — so any Langfuse handler from the parent leaks into
    the child graph and records duplicate observations on the wrong trace.

    Passing a non-empty list (even with a no-op handler) forces LangChain
    to create a fresh ``CallbackManager`` with only our handlers, blocking
    inheritance from the parent.
    """


# ── ContextVar Definition ─────────────────────────────────────────────────────

class BabelfishContextData(TypedDict):
    mode: str                  # "baseline" | "babelfish"
    flow_id: str               # X-Flow-ID header for babelfish routing
    subflow_server_ids: dict   # system_message_content → msg_hash (identifies tracked subflows)
    subflow_invocations: list  # accumulator: list[{msg_hash, client_trace_id, server_session_id}]


babelfish_context: contextvars.ContextVar[Optional[BabelfishContextData]] = contextvars.ContextVar(
    "babelfish_context", default=None
)


# ── Subflow Helpers ───────────────────────────────────────────────────────────
# Subflow identification is still ContextVar-based because ``subflow_server_ids``
# is cross-cutting (the same map applies to every LLM call inside one
# adapter.run()).  Session identity is NOT in the ContextVar — the helper
# below mints fresh UUIDs at every invocation and returns them to the caller,
# who passes them explicitly to ``LLMAPI.get_model()``.

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


def mint_flow_session(system_message_content: str) -> tuple[str, list]:
    """Mint a fresh ``session_id`` for one flow role invocation.

    Called once per flow entry point: top-level ``adapter.run()`` mints one
    for the parent flow, and every sub-agent / node function mints its own
    when it starts making LLM calls.  The returned ``session_id`` is a fresh
    UUID4 that the caller MUST pass to every ``LLMAPI.get_model`` call within
    its scope — there is no ContextVar fallback.

    If the given system_message_content is registered as a tracked subflow in
    ``babelfish_context["subflow_server_ids"]``, the call is recorded in
    ``subflow_invocations`` (for ``__trace_metadata__``) and Langfuse callbacks
    scoped to this invocation are returned.  Otherwise the call is considered
    parent-flow work — no tracked row is recorded, and the returned callbacks
    list is empty (the parent's own callbacks come from ``adapter.run()``).

    Returns:
        (session_id, callbacks) — the caller passes ``session_id`` to every
        ``LLMAPI.get_model`` call in its scope, and threads ``callbacks``
        into the RunnableConfig for graph invocations so Langfuse traces land
        on the right client trace id.
    """
    session_id = str(_uuid.uuid4())

    parent_ctx = babelfish_context.get()
    if not parent_ctx:
        # Running outside the adapter (tests, CLI). Caller still gets a
        # session_id so the LLM call site has one to pass.
        # Return isolation handler to prevent parent-callback leakage.
        return session_id, [_CallbackIsolationHandler()]

    msg_hash = _is_tracked_subflow(system_message_content)
    if not msg_hash:
        # Parent flow work — the adapter's own callbacks already trace this.
        # Return isolation handler to prevent parent-callback leakage.
        return session_id, [_CallbackIsolationHandler()]

    client_trace_id = str(_uuid.uuid4()).replace("-", "")
    parent_ctx["subflow_invocations"].append({
        "msg_hash": msg_hash,
        "client_trace_id": client_trace_id,
        "server_session_id": session_id,
    })
    callbacks = _build_subflow_callback(client_trace_id)
    return session_id, callbacks
