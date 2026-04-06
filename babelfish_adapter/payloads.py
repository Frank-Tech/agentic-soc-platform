from typing import List

from babelfish_adapter.entries import get_entry_ids


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


def list_payloads() -> List[str]:
    names = []
    for entry_id in get_entry_ids():
        for alert_name in _ALERT_NAMES:
            names.append(f"{entry_id}:{alert_name}")
    return names


def parse_payload_name(payload_name: str) -> tuple:
    if ":" not in payload_name:
        raise ValueError(f"Invalid payload_name: {payload_name}. Expected 'entry_id:alert_name'.")
    entry_id, alert_name = payload_name.split(":", 1)
    return entry_id, alert_name


def get_alert_by_name(alert_name: str):
    from PLUGINS.Mock.SIRP import mock_alert

    if not hasattr(mock_alert, alert_name):
        raise ValueError(f"Unknown alert: {alert_name}")
    return getattr(mock_alert, alert_name)
