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


babelfish_context: contextvars.ContextVar[Optional[BabelfishContextData]] = contextvars.ContextVar(
    "babelfish_context", default=None
)


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
        return [CallbackHandler(public_key=pub, trace_context={"trace_id": trace_id})]
    except Exception:
        return []


def flush_callbacks(callbacks: list) -> None:
    for cb in callbacks:
        if hasattr(cb, "_langfuse_client"):
            try:
                cb._langfuse_client.flush()
            except Exception:
                pass
