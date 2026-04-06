from typing import Dict, Type

from Lib.baseplaybook import LanggraphPlaybook


_DATA_DIR_OVERRIDES = {
    "l3_with_tools": "Case_L3_SOC_Analyst_Agent_With_Tools",
    "threat_hunting": "Case_Threat_Hunting_Agent",
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

    _entries_cache["l3_with_tools"] = L3WithToolsPlaybook
    _entries_cache["threat_hunting"] = ThreatHuntingPlaybook
    return _entries_cache


def get_entry_ids() -> list:
    return ["l3_with_tools", "threat_hunting"]


def get_playbook_class(entry_id: str) -> Type[LanggraphPlaybook]:
    entries = _load_entries()
    if entry_id not in entries:
        raise ValueError(f"Unknown entry_id: {entry_id}. Valid: {list(entries.keys())}")
    return entries[entry_id]
