import random
import uuid
from datetime import datetime

from PLUGINS.Mock.SIEM import settings


class SQLInjectionScenario(object):
    def __init__(self):
        self.attacker_ip = "45.95.11.22"
        self.target_domain = "web-3.example.com"
        self.session_id = str(uuid.uuid4())

    def get_logs(self) -> list:
        logs = []
        sqli_payloads = [
            "' OR 1=1--",
            "'; DROP TABLE users;--",
            "' UNION SELECT username,password FROM users--",
            "1' AND (SELECT COUNT(*) FROM information_schema.tables)>0--",
            "admin'/*",
        ]
        paths = [
            "/api/v1/users?id=",
            "/api/v2/search?q=",
            "/api/v2/auth/login",
            "/admin/dashboard?filter=",
        ]

        for i, payload in enumerate(sqli_payloads):
            path = random.choice(paths)
            is_post = "login" in path
            logs.append({
                "@timestamp": datetime.utcnow().isoformat() + "Z",
                "event.dataset": "waf",
                "event.module": "waf",
                "event.category": "intrusion_detection",
                "event.action": "blocked",
                "event.outcome": "failure",
                "rule.id": "WAF-RULE-SQLI-001",
                "rule.name": "SQL Injection Detection",
                "rule.category": "sqli",
                "http.request.method": "POST" if is_post else "GET",
                "http.request.path": path,
                "http.request.query": "" if is_post else payload,
                "http.request.body": payload if is_post else "",
                "http.response.status_code": 403,
                "http.version": "1.1",
                "source.ip": self.attacker_ip,
                "source.geo.country_name": "China",
                "source.geo.country_iso_code": "CN",
                "destination.ip": random.choice(settings.INTERNAL_IPS),
                "destination.port": 443,
                "url.domain": self.target_domain,
                "user_agent.original": "sqlmap/1.7.12#stable (https://sqlmap.org)",
                "threat.indicator.confidence": "critical",
                "log.level": "critical",
            })

        return logs
