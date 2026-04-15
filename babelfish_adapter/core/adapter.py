# ═══════════════════════════════════════════════════════════════════════════════
# BABELFISH ADAPTER — agentic-soc-platform
# ═══════════════════════════════════════════════════════════════════════════════
#
# This file implements the 3 functions that lexus-test calls to run external
# flows through the babelfish proxy:
#
#   run(...)           — execute a flow, yield LangGraph-style steps
#   list_payloads()    — return all testable payload names
#   list_flow_groups() — return flow/subflow metadata for trace mapping
#
# STRUCTURE:
#   The file is split into two clear halves:
#
#   1. BABELFISH BOILERPLATE (KEEP AS-IS)
#      Generic run wrapper that handles context setup, Langfuse callbacks,
#      trace metadata, and cleanup. Copy this unchanged to any project.
#
#   2. PROJECT-SPECIFIC (CUSTOMIZE)
#      Your project's entries, payloads, flow groups, input builders, and
#      the execute_flow() function. Rewrite this entirely for your project.
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import uuid
from typing import AsyncGenerator, Dict, Type, List, Any

from babelfish_adapter.core.context import babelfish_context


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  PART 1: BABELFISH BOILERPLATE — KEEP AS-IS                            ║
# ║                                                                         ║
# ║  Generic wrapper that any project copies unchanged.                     ║
# ║  Handles: context setup, Langfuse callbacks, trace metadata, cleanup.   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


def _build_langfuse_callbacks(trace_id: str) -> tuple[list, object | None]:
    """Build Langfuse callbacks for the main flow's trace."""
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
    flow_id: str,
    payload_name: str,
    subflow_server_ids: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Execute a flow and yield LangGraph-style steps.             KEEP AS-IS

    This is the generic run wrapper. It:
      1. Validates mode
      2. Mints the parent flow's session_id (UUID4) and Langfuse trace_id
      3. Builds Langfuse callbacks for the parent flow
      4. Sets babelfish_context (mode / flow_id / subflow bookkeeping only —
         session_id is NOT in the context; every flow role mints its own and
         passes it explicitly to LLMAPI.get_model)
      5. Calls YOUR execute_flow() to do the actual work
      6. Collects per-invocation subflow trace records
      7. Yields __trace_metadata__ with the parent session_id + subflows
      8. Cleans up (flushes Langfuse, resets context)

    The only project-specific part is execute_flow() — see PART 2 below.

    lexus-test no longer pre-mints a session_id and passes it in; the adapter
    owns minting and reports every session back via ``__trace_metadata__``.
    """
    if mode not in ("baseline", "babelfish"):
        raise ValueError(f"Invalid mode: {mode}. Expected 'baseline' or 'babelfish'.")

    # Parent flow's identity — minted here, reported back via __trace_metadata__.
    parent_session_id = str(uuid.uuid4())
    parent_client_trace_id = str(uuid.uuid4()).replace("-", "")

    callbacks, main_handler = _build_langfuse_callbacks(parent_client_trace_id)

    subflow_invocations: list = []
    token = babelfish_context.set(
        {
            "mode": mode,
            "flow_id": flow_id,
            "subflow_server_ids": subflow_server_ids or {},
            "subflow_invocations": subflow_invocations,
        }
    )

    try:
        # ── This is the only line that calls your project's code ──
        async for step in execute_flow(
            payload_name=payload_name,
            session_id=parent_session_id,
            callbacks=callbacks,
        ):
            yield step

        actual_trace_id = (
            main_handler.last_trace_id if main_handler and main_handler.last_trace_id
            else parent_client_trace_id
        )

        yield {
            "__trace_metadata__": {
                "session_id": parent_session_id,
                "client_trace_id": actual_trace_id,
                "server_trace_id": parent_session_id.replace("-", ""),
                "subflow_invocations": subflow_invocations,
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


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  PART 2: PROJECT-SPECIFIC — CUSTOMIZE                                  ║
# ║                                                                         ║
# ║  Everything below is specific to agentic-soc-platform.                  ║
# ║  For a new project, rewrite this entire section.                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝


# ── REGISTRY ─────────────────────────────────────────────────────────────────
# In-memory store for mock entities. During adapter execution, playbooks call
# SIRP's get() method which is monkey-patched (in project/bootstrap.py) to
# look up entities from this registry instead of hitting the real SIRP API.

_registry: Dict[str, Any] = {}


def register(rowid: str, entity: Any) -> None:
    _registry[rowid] = entity


def lookup(rowid: str) -> Any:
    return _registry.get(rowid)


def unregister(rowid: str) -> None:
    _registry.pop(rowid, None)


# ── ENTRIES ──────────────────────────────────────────────────────────────────
# Map entry_id strings to playbook/module classes.

from Lib.baseplaybook import LanggraphPlaybook

_DATA_DIR_OVERRIDES = {
    "l3_with_tools": "Case_L3_SOC_Analyst_Agent_With_Tools",
    "threat_hunting": "Case_Threat_Hunting_Agent",
}

# Sub-agents (used as tools by parent playbooks) — Python module name → DATA dir.
# Required because Python modules are snake_case but DATA dirs are PascalCase,
# which matters on case-sensitive filesystems (Linux).
_SUBAGENT_DATA_DIR_OVERRIDES = {
    "agent_siem": "Agent_SIEM",
    "agent_threat_intelligence": "Agent_Threat_Intelligence",
}

_entries_cache: Dict[str, Type[LanggraphPlaybook]] = {}


def _patch_module_name(cls: Type[LanggraphPlaybook], data_dir_name: str) -> None:
    if getattr(cls, "_adapter_module_name_patched", False):
        return
    cls.module_name = property(lambda self, _name=data_dir_name: _name)
    cls._adapter_module_name_patched = True


def _load_entries() -> Dict[str, Type[LanggraphPlaybook]]:
    if _entries_cache:
        return _entries_cache

    from PLAYBOOKS.CASE.L3_SOC_Analyst_Agent_With_Tools import Playbook as L3WithToolsPlaybook
    from PLAYBOOKS.CASE.Threat_Hunting_Agent import Playbook as ThreatHuntingPlaybook

    _patch_module_name(L3WithToolsPlaybook, _DATA_DIR_OVERRIDES["l3_with_tools"])
    _patch_module_name(ThreatHuntingPlaybook, _DATA_DIR_OVERRIDES["threat_hunting"])

    # Patch sub-agent classes too — they use load_system_prompt_template
    # which derives the path from self.module_name (Python module name).
    from AGENTS.agent_siem import GraphAgent as SiemGraphAgent
    from AGENTS.agent_threat_intelligence import GraphAgent as ThreatIntelGraphAgent

    _patch_module_name(SiemGraphAgent, _SUBAGENT_DATA_DIR_OVERRIDES["agent_siem"])
    _patch_module_name(ThreatIntelGraphAgent, _SUBAGENT_DATA_DIR_OVERRIDES["agent_threat_intelligence"])

    _entries_cache["l3_with_tools"] = L3WithToolsPlaybook
    _entries_cache["threat_hunting"] = ThreatHuntingPlaybook
    return _entries_cache


def _get_entry_ids() -> list:
    return ["l3_with_tools", "threat_hunting"]


def _get_playbook_class(entry_id: str) -> Type[LanggraphPlaybook]:
    entries = _load_entries()
    if entry_id not in entries:
        raise ValueError(f"Unknown entry_id: {entry_id}. Valid: {list(entries.keys())}")
    return entries[entry_id]


# ── PAYLOADS ─────────────────────────────────────────────────────────────────
# Available test inputs. Format: "entry_id:payload_name".

_ALERT_NAMES = [
    "alert_user_reported_phishing",
    "alert_malware_blocked",
    "alert_psexec_lateral",
    "alert_credential_dumping",
    "alert_dns_tunnel_volume",
    "alert_dns_long_query",
    "alert_brute_force_ssh",
    "alert_malware_execution",
    "alert_unauthorized_access",
    "alert_data_exfiltration",
    "alert_malicious_email_attachment",
    "alert_privilege_escalation",
    "alert_cloud_config_change",
    "alert_brute_force_siem",
    "alert_sql_injection_siem",
    "alert_ransomware_siem",
]


def _parse_payload_name(payload_name: str) -> tuple:
    if ":" not in payload_name:
        raise ValueError(f"Invalid payload_name: {payload_name}. Expected 'entry_id:alert_name'.")
    entry_id, alert_name = payload_name.split(":", 1)
    return entry_id, alert_name


def _get_alert_by_name(alert_name: str):
    from PLUGINS.Mock.SIRP import mock_alert
    if not hasattr(mock_alert, alert_name):
        raise ValueError(f"Unknown alert: {alert_name}")
    return getattr(mock_alert, alert_name)


# ── FLOW GROUPS ──────────────────────────────────────────────────────────────
# Flow/subflow relationships for trace mapping.

from Lib.configs import DATA_DIR

_FLOW_GROUPS = [
    {
        "entry_id": "l3_with_tools",
        "flow": {"name": "l3_with_tools", "prompt_dir": "Case_L3_SOC_Analyst_Agent_With_Tools", "prompt_file": "L3_SOC_Analyst.md"},
        "subflows": [
            {"name": "agent_siem", "prompt_dir": "Agent_SIEM"},
        ],
    },
    {
        "entry_id": "threat_hunting",
        "flow": {"name": "threat_hunting", "prompt_dir": "Case_Threat_Hunting_Agent", "prompt_file": "Intent_System.md"},
        "subflows": [
            {"name": "agent_siem", "prompt_dir": "Agent_SIEM"},
            {"name": "agent_threat_intelligence", "prompt_dir": "Agent_Threat_Intelligence"},
        ],
    },
]


def _read_prompt(subdir: str, filename: str = "system_prompt.md") -> str:
    path = os.path.join(DATA_DIR, subdir, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── INPUT BUILDERS ───────────────────────────────────────────────────────────
# Convert a raw payload (alert) into the input format your playbook expects.

from PLUGINS.SIRP.sirpmodel import (
    AlertModel, CaseModel, CaseStatus, CasePriority,
    ProductCategory, Severity, ImpactLevel, Confidence,
)

_SEVERITY_TO_PRIORITY = {
    Severity.INFORMATIONAL: CasePriority.LOW,
    Severity.LOW: CasePriority.LOW,
    Severity.MEDIUM: CasePriority.MEDIUM,
    Severity.HIGH: CasePriority.HIGH,
    Severity.CRITICAL: CasePriority.CRITICAL,
}


def _build_case_from_alert(alert: AlertModel) -> CaseModel:
    rowid = str(uuid.uuid4())
    category = alert.product_category if alert.product_category is not None else ProductCategory.OTHERS
    return CaseModel(
        rowid=rowid,
        title=f"Case: {alert.title}",
        severity=alert.severity if alert.severity is not None else Severity.MEDIUM,
        impact=alert.impact if alert.impact is not None else ImpactLevel.MEDIUM,
        priority=_SEVERITY_TO_PRIORITY.get(alert.severity, CasePriority.MEDIUM),
        confidence=alert.confidence if alert.confidence is not None else Confidence.MEDIUM,
        description=alert.desc or alert.title,
        category=category,
        tags=list(alert.labels) if alert.labels else [],
        status=CaseStatus.IN_PROGRESS,
        comment="Case synthesized from alert for babelfish testing.",
        correlation_uid=alert.correlation_uid,
        summary="",
        workbook="",
        comment_ai="",
        summary_ai="",
        attack_stage_ai=None,
        threat_hunting_report_ai="",
        tickets=[],
        enrichments=list(alert.enrichments) if alert.enrichments else [],
        alerts=[alert],
    )


# ── EXECUTE FLOW ─────────────────────────────────────────────────────────────
# This is the function that run() calls. It does the actual project-specific
# work: parse the payload, build input, instantiate the playbook, stream it.
#
# For a new project, this is the main function you write. It receives:
#   - payload_name: which test input to use
#   - session_id: for thread_id / checkpointer
#   - callbacks: Langfuse callbacks to pass to RunnableConfig
#
# It must be an async generator that yields LangGraph steps.

async def execute_flow(
    *,
    payload_name: str,
    session_id: str,
    callbacks: list,
) -> AsyncGenerator[dict, None]:
    """Run a playbook and yield its LangGraph steps."""
    entry_id, alert_name = _parse_payload_name(payload_name)
    alert = _get_alert_by_name(alert_name)
    case = _build_case_from_alert(alert)

    from PLUGINS.SIRP.sirpmodel import PlaybookModel
    from langchain_core.runnables import RunnableConfig

    playbook_rowid = str(uuid.uuid4())
    playbook_model = PlaybookModel(
        rowid=playbook_rowid,
        source_rowid=case.rowid,
        user_input="",
    )

    register(case.rowid, case)
    register(playbook_rowid, playbook_model)

    try:
        PlaybookClass = _get_playbook_class(entry_id)
        playbook = PlaybookClass()
        playbook._playbook_model = playbook_model

        config = RunnableConfig(
            configurable={"thread_id": session_id, "session_id": session_id},
            callbacks=callbacks,
        )

        from Lib.llmapi import BaseAgentState

        initial_state = playbook.agent_state if playbook.agent_state is not None else BaseAgentState()

        async for step in playbook.graph.astream(initial_state, config):
            yield step
    finally:
        unregister(case.rowid)
        unregister(playbook_rowid)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTRACT FUNCTIONS — list_payloads() and list_flow_groups()
# ═══════════════════════════════════════════════════════════════════════════════


def list_payloads() -> List[str]:
    """Return all testable payload names.                            CUSTOMIZE

    Called once at registration time by lexus-test to discover what
    payloads this adapter supports. Format: "entry_id:payload_name".
    """
    names = []
    for entry_id in _get_entry_ids():
        for alert_name in _ALERT_NAMES:
            names.append(f"{entry_id}:{alert_name}")
    return names


def list_flow_groups() -> List[Dict]:
    """Return flow/subflow metadata for trace mapping.               CUSTOMIZE

    Called by lexus-test to discover subflows and their system prompts.
    lexus-test uses system_message content as keys in subflow_server_ids,
    enabling per-subflow trace separation. Each subflow entry point mints
    its own UUID4 session_id via ``mint_flow_session()`` (see
    ``babelfish_adapter/core/context.py``).
    """
    result = []
    for group in _FLOW_GROUPS:
        flow_def = group["flow"]
        entry = {
            "entry_id": group["entry_id"],
            "flow": {
                "name": flow_def["name"],
                "system_message": _read_prompt(flow_def["prompt_dir"], flow_def.get("prompt_file", "system_prompt.md")),
            },
            "subflows": [
                {
                    "name": sf["name"],
                    "system_message": _read_prompt(sf["prompt_dir"]),
                }
                for sf in group["subflows"]
            ],
        }
        result.append(entry)
    return result
