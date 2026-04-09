import contextvars
import os
from typing import Optional, TypedDict


class BabelfishContextData(TypedDict):
    mode: str
    session_id: str
    trace_id: str
    flow_id: str
    callbacks: list
    trace_mapping: dict
    subflow_handlers: dict
    subflow_server_ids: dict


babelfish_context: contextvars.ContextVar[Optional[BabelfishContextData]] = contextvars.ContextVar(
    "babelfish_context", default=None
)


def get_subflow_server_context(system_message_content: str) -> dict | None:
    """Get overridden session_id for a subflow so it gets its own holy-grail trace.

    The subflow_server_ids mapping uses msg_hash as value (unique per subflow),
    ensuring multi-subflow flows don't collide on the same X-Session-ID.

    Returns {"session_id": str} if a mapping exists, None otherwise.
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
    for cb in callbacks:
        if hasattr(cb, "_langfuse_client"):
            try:
                cb._langfuse_client.flush()
            except Exception:
                pass
