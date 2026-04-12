import random
from datetime import datetime

from PLUGINS.Mock.SIEM import settings


class WAFGenerator:
    METHODS = [
        {"method": "GET", "weight": 50},
        {"method": "POST", "weight": 30},
        {"method": "PUT", "weight": 10},
        {"method": "DELETE", "weight": 5},
        {"method": "OPTIONS", "weight": 5},
    ]

    PATHS = [
        "/api/v1/users", "/api/v1/products", "/api/v1/orders",
        "/api/v2/search", "/api/v2/auth/login", "/api/v2/auth/register",
        "/admin/dashboard", "/admin/settings", "/static/js/app.js",
        "/images/logo.png", "/health", "/metrics",
    ]

    DOMAINS = [
        "web-1.example.com", "web-2.example.com", "web-3.example.com",
        "api.example.com", "app.example.com",
    ]

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/17.2",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "curl/8.4.0",
        "python-requests/2.31.0",
    ]

    RULES = [
        {"id": "WAF-RULE-GENERAL-001", "name": "Rate Limit", "category": "rate_limit", "action": "logged", "weight": 40},
        {"id": "WAF-RULE-GENERAL-002", "name": "Geo Block", "category": "geo_block", "action": "allowed", "weight": 30},
        {"id": "WAF-RULE-GENERAL-003", "name": "Bot Detection", "category": "scanner", "action": "allowed", "weight": 20},
        {"id": "WAF-RULE-GENERAL-004", "name": "IP Reputation", "category": "reputation", "action": "allowed", "weight": 10},
    ]

    @classmethod
    def generate(cls):
        m = random.choices(cls.METHODS, weights=[x["weight"] for x in cls.METHODS])[0]
        r = random.choices(cls.RULES, weights=[x["weight"] for x in cls.RULES])[0]
        src_ip = random.choice(settings.EXTERNAL_IPS)
        dst_ip = random.choice(settings.INTERNAL_IPS)

        return {
            "@timestamp": datetime.utcnow().isoformat() + "Z",
            "event.dataset": "waf",
            "event.module": "waf",
            "event.category": "web",
            "event.action": r["action"],
            "event.outcome": "success",
            "rule.id": r["id"],
            "rule.name": r["name"],
            "rule.category": r["category"],
            "http.request.method": m["method"],
            "http.request.path": random.choice(cls.PATHS),
            "http.request.query": "",
            "http.request.body": "",
            "http.response.status_code": 200,
            "http.version": "1.1",
            "source.ip": src_ip,
            "source.geo.country_name": random.choice(["United States", "Germany", "Japan", "Brazil", "India"]),
            "source.geo.country_iso_code": random.choice(["US", "DE", "JP", "BR", "IN"]),
            "destination.ip": dst_ip,
            "destination.port": random.choice([443, 80]),
            "url.domain": random.choice(cls.DOMAINS),
            "user_agent.original": random.choice(cls.USER_AGENTS),
            "threat.indicator.confidence": "low",
            "log.level": "info",
        }
