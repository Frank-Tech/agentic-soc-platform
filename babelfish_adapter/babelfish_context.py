import contextvars
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
