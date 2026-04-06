import os
import uuid
from typing import AsyncGenerator

from langchain_core.runnables import RunnableConfig

from asp_adapter import bootstrap  # noqa: F401
from asp_adapter.babelfish_context import babelfish_context
from asp_adapter.entries import get_playbook_class
from asp_adapter.input_builders import build_case_from_alert
from asp_adapter.payloads import get_alert_by_name, parse_payload_name
from asp_adapter.registry import register, unregister


def _reset_subagent_singletons() -> None:
    try:
        from AGENTS import agent_siem
        agent_siem._graph_agent_instance = None
    except Exception:
        pass
    try:
        from AGENTS import agent_threat_intelligence
        agent_threat_intelligence._graph_agent_instance = None
    except Exception:
        pass


def _build_langfuse_callbacks(trace_id: str) -> list:
    pub = os.environ.get("CLIENT_LANGFUSE_PUBLIC_KEY")
    sec = os.environ.get("CLIENT_LANGFUSE_SECRET_KEY")
    host = os.environ.get("CLIENT_LANGFUSE_HOST")
    if not (pub and sec and host):
        return []
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse(public_key=pub, secret_key=sec, base_url=host)
    handler = CallbackHandler(public_key=pub, trace_context={"trace_id": trace_id})
    return [handler]


async def run(
    *,
    mode: str,
    session_id: str,
    trace_id: str,
    flow_id: str,
    payload_name: str,
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

    _reset_subagent_singletons()

    token = babelfish_context.set(
        {
            "mode": mode,
            "session_id": session_id,
            "trace_id": trace_id,
            "flow_id": flow_id,
        }
    )

    try:
        PlaybookClass = get_playbook_class(entry_id)
        playbook = PlaybookClass()
        playbook._playbook_model = playbook_model

        callbacks = _build_langfuse_callbacks(trace_id)
        config = RunnableConfig(configurable={"thread_id": session_id}, callbacks=callbacks)

        from Lib.llmapi import BaseAgentState

        initial_state = playbook.agent_state if playbook.agent_state is not None else BaseAgentState()

        async for step in playbook.graph.astream(initial_state, config):
            yield step
    finally:
        try:
            babelfish_context.reset(token)
        except ValueError:
            babelfish_context.set(None)
        unregister(case.rowid)
        unregister(playbook_rowid)
