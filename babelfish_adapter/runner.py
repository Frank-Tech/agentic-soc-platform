import os
import uuid
from typing import AsyncGenerator

from langchain_core.runnables import RunnableConfig

from babelfish_adapter import bootstrap  # noqa: F401
from babelfish_adapter.babelfish_context import babelfish_context
from babelfish_adapter.entries import get_playbook_class
from babelfish_adapter.input_builders import build_case_from_alert
from babelfish_adapter.payloads import get_alert_by_name, parse_payload_name
from babelfish_adapter.registry import register, unregister


def _build_langfuse_callbacks(trace_id: str) -> tuple[list, object | None]:
    pub = os.environ.get("CLIENT_LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("CLIENT_LANGFUSE_SECRET_KEY")
    host = os.environ.get("CLIENT_LANGFUSE_HOST")
    if not (pub and sec and host):
        return [], None
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(public_key=pub, secret_key=sec, base_url=host)
    handler = CallbackHandler(public_key=pub, trace_context={"trace_id": trace_id})
    return [handler], handler


async def run(
    *,
    mode: str,
    session_id: str,
    trace_id: str,
    flow_id: str,
    payload_name: str,
    trace_mapping: dict | None = None,
) -> AsyncGenerator[dict, None]:
    if mode not in ("baseline", "babelfish"):
        raise ValueError(f"Invalid mode: {mode}. Expected 'baseline' or 'babelfish'.")

    entry_id, alert_name = parse_payload_name(payload_name)
    alert = get_alert_by_name(alert_name)
    case = build_case_from_alert(alert)

    from PLUGINS.SIRP.sirpmodel import PlaybookModel

    playbook_rowid = str(uuid.uuid4())
    playbook_model = PlaybookModel(
        rowid=playbook_rowid,
        source_rowid=case.rowid,
        user_input="",
    )

    register(case.rowid, case)
    register(playbook_rowid, playbook_model)

    callbacks, main_handler = _build_langfuse_callbacks(trace_id)

    subflow_handlers: dict = {}
    token = babelfish_context.set(
        {
            "mode": mode,
            "session_id": session_id,
            "trace_id": trace_id,
            "flow_id": flow_id,
            "callbacks": callbacks,
            "trace_mapping": trace_mapping or {},
            "subflow_handlers": subflow_handlers,
        }
    )

    try:
        PlaybookClass = get_playbook_class(entry_id)
        playbook = PlaybookClass()
        playbook._playbook_model = playbook_model

        config = RunnableConfig(configurable={"thread_id": session_id}, callbacks=callbacks)

        from Lib.llmapi import BaseAgentState

        initial_state = playbook.agent_state if playbook.agent_state is not None else BaseAgentState()

        async for step in playbook.graph.astream(initial_state, config):
            yield step

        actual_trace_id = (
            main_handler.last_trace_id if main_handler and main_handler.last_trace_id
            else trace_id
        )
        subflow_trace_ids = {}
        for content_key, h in subflow_handlers.items():
            if hasattr(h, "last_trace_id") and h.last_trace_id:
                subflow_trace_ids[content_key] = h.last_trace_id
        yield {
            "__trace_metadata__": {
                "client_trace_id": actual_trace_id,
                "subflow_trace_ids": subflow_trace_ids,
            }
        }
    finally:
        for cb in callbacks:
            if hasattr(cb, "_langfuse_client"):
                try:
                    cb._langfuse_client.flush()
                except Exception:
                    pass
        try:
            babelfish_context.reset(token)
        except ValueError:
            babelfish_context.set(None)
        unregister(case.rowid)
        unregister(playbook_rowid)
