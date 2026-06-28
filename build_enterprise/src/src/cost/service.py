# cost/service.py – Cost tracking, anomaly detection, budget alerts
import json
import os
import time
import threading
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import hashlib
import requests

class CostMonitor:
    def __init__(self, config_path: str = "config/cost/config.json"):
        self.config = self._load_config(config_path)
        self.historical_costs = deque(maxlen=90)  # last 90 days
        self.daily_costs = {}
        self.anomaly_history = []
        self.budget_alerts = []
        self._load_historical()
        self._start_monitoring()
    
    def _load_config(self, path):
        default = {
            "budget": {
                "monthly_limit_usd": 5000,
                "tier_limits": {
                    "free_pay_per_use": 100,
                    "basic": 500,
                    "pro": 2000,
                    "enterprise": 10000
                },
                "alert_thresholds": [0.5, 0.75, 0.9, 0.95, 1.0]
            },
            "anomaly": {
                "zscore_threshold": 2.5,
                "iqr_threshold": 1.5,
                "window_days": 14,
                "sensitivity": "medium"
            },
            "alerts": {
                "email": {"enabled": False, "recipients": ["admin@crownstar.ai"]},
                "slack": {"enabled": False, "webhook_url": ""},
                "webhook": {"enabled": False, "url": ""}
            },
            "cloud_provider": "aws",
            "billing_api_key": "",
            "cost_retention_days": 365
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _load_historical(self):
        hist_file = "data/cost/historical.json"
        if os.path.exists(hist_file):
            with open(hist_file, 'r') as f:
                data = json.load(f)
                self.daily_costs = data.get("daily", {})
                for date_str, cost in self.daily_costs.items():
                    self.historical_costs.append(cost)
    
    def _save_historical(self):
        with open("data/cost/historical.json", "w") as f:
            json.dump({"daily": self.daily_costs, "last_updated": datetime.utcnow().isoformat()}, f)
    
    def _start_monitoring(self):
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
    
    def _monitoring_loop(self):
        while True:
            try:
                # Fetch today's cost from cloud provider (stub)
                today = datetime.utcnow().date().isoformat()
                cost = self._fetch_todays_cost()
                if cost is not None:
                    self.daily_costs[today] = cost
                    self.historical_costs.append(cost)
                    self._save_historical()
                    # Check budget and anomalies
                    self._check_budget(cost)
                    self._detect_anomaly(cost, today)
                time.sleep(3600)  # check every hour
            except Exception as e:
                print(f"Cost monitoring error: {e}")
                time.sleep(3600)
    
    def _fetch_todays_cost(self) -> Optional[float]:
        """Stub – in production, query cloud billing API (AWS Cost Explorer, Azure Consumption, GCP Billing)"""
        provider = self.config.get("cloud_provider", "none")
        if provider == "aws":
            # Placeholder – would use boto3 ce.get_cost_and_usage
            pass
        elif provider == "azure":
            pass
        elif provider == "gcp":
            pass
        # For simulation, generate random cost (0-50 USD per day)
        import random
        return random.uniform(10, 200)
    
    def _detect_anomaly(self, cost: float, date_str: str):
        window = self.config["anomaly"]["window_days"]
        if len(self.historical_costs) < window:
            return
        recent = list(self.historical_costs)[-window:]
        mean = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return
        zscore = abs(cost - mean) / std
        iqr = np.percentile(recent, 75) - np.percentile(recent, 25)
        iqr_dev = (cost - mean) / (iqr + 1e-9)
        threshold_z = self.config["anomaly"]["zscore_threshold"]
        threshold_iqr = self.config["anomaly"]["iqr_threshold"]
        is_anomaly = zscore > threshold_z or abs(iqr_dev) > threshold_iqr
        if is_anomaly:
            anomaly = {
                "date": date_str,
                "cost": cost,
                "expected_mean": mean,
                "zscore": zscore,
                "iqr_deviation": iqr_dev,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.anomaly_history.append(anomaly)
            self._send_alert("cost_anomaly", anomaly)
            # Trim history
            if len(self.anomaly_history) > 100:
                self.anomaly_history = self.anomaly_history[-50:]
            print(f"⚠️ Cost anomaly detected: ${cost:.2f} (expected ${mean:.2f})")
    
    def _check_budget(self, daily_cost: float):
        month = datetime.utcnow().strftime("%Y-%m")
        month_costs = [self.daily_costs[d] for d in self.daily_costs if d.startswith(month)]
        total_month = sum(month_costs)
        limit = self.config["budget"]["monthly_limit_usd"]
        usage_ratio = total_month / limit if limit > 0 else 0
        
        # Check tier budgets (from analytics)
        from analytics.analytics_service import get_analytics_service
        analytics = get_analytics_service()
        # Get cost by tier for current month (simplified)
        start_date = f"{month}-01"
        end_date = datetime.utcnow().date().isoformat()
        by_tier = analytics.get_usage_by_tier(start_date, end_date)
        tier_limits = self.config["budget"]["tier_limits"]
        for tier, data in by_tier.items():
            tier_cost = data.get("cost", 0)
            tier_limit = tier_limits.get(tier, 0)
            if tier_limit > 0 and tier_cost > tier_limit:
                self._send_alert("tier_budget_exceeded", {"tier": tier, "cost": tier_cost, "limit": tier_limit})
        
        # Check alert thresholds
        for threshold in self.config["budget"]["alert_thresholds"]:
            if usage_ratio >= threshold and threshold not in [a.get("threshold") for a in self.budget_alerts if a.get("month") == month]:
                self._send_alert("budget_threshold", {"usage_ratio": usage_ratio, "threshold": threshold, "total": total_month, "limit": limit})
                self.budget_alerts.append({"month": month, "threshold": threshold, "timestamp": datetime.utcnow().isoformat()})
    
    def _send_alert(self, alert_type: str, data: Dict):
        alerts_cfg = self.config["alerts"]
        message = self._format_alert_message(alert_type, data)
        
        # Email alert
        if alerts_cfg["email"]["enabled"]:
            self._send_email(alerts_cfg["email"]["recipients"], f"CrownStar Cost Alert: {alert_type}", message)
        # Slack alert
        if alerts_cfg["slack"]["enabled"]:
            self._send_slack(alerts_cfg["slack"]["webhook_url"], message)
        # Webhook alert
        if alerts_cfg["webhook"]["enabled"]:
            self._send_webhook(alerts_cfg["webhook"]["url"], {"type": alert_type, "data": data})
    
    def _format_alert_message(self, alert_type: str, data: Dict) -> str:
        if alert_type == "cost_anomaly":
            return f"CrownStar cost anomaly: ${data['cost']:.2f} vs expected ${data['expected_mean']:.2f} (z={data['zscore']:.2f}) on {data['date']}"
        elif alert_type == "budget_threshold":
            return f"Budget threshold {data['threshold']*100:.0f}% reached: ${data['total']:.2f} of ${data['limit']:.2f} this month"
        elif alert_type == "tier_budget_exceeded":
            return f"Tier {data['tier']} exceeded budget: ${data['cost']:.2f} > ${data['limit']:.2f}"
        return "CrownStar cost alert"
    
    def _send_email(self, recipients: List[str], subject: str, body: str):
        # Stub – integrate with SMTP
        print(f"Email alert: {subject} -> {recipients}")
    
    def _send_slack(self, webhook_url: str, message: str):
        try:
            requests.post(webhook_url, json={"text": message}, timeout=5)
        except:
            pass
    
    def _send_webhook(self, url: str, payload: Dict):
        try:
            requests.post(url, json=payload, timeout=5)
        except:
            pass
    
    def get_status(self) -> Dict:
        month = datetime.utcnow().strftime("%Y-%m")
        month_costs = [self.daily_costs[d] for d in self.daily_costs if d.startswith(month)]
        total_month = sum(month_costs)
        limit = self.config["budget"]["monthly_limit_usd"]
        return {
            "current_month": month,
            "total_cost_usd": round(total_month, 2),
            "budget_limit_usd": limit,
            "usage_percentage": round(total_month / limit * 100, 1) if limit > 0 else 0,
            "daily_costs": {d: self.daily_costs[d] for d in sorted(self.daily_costs.keys())[-30:]},
            "anomalies_last_30_days": len(self.anomaly_history),
            "budget_alerts": self.budget_alerts
        }
    
    def forecast_next_month(self) -> float:
        """Simple linear regression forecast"""
        if len(self.historical_costs) < 30:
            return 0
        days = list(range(len(self.historical_costs)))
        costs = list(self.historical_costs)
        # Linear regression
        x = np.array(days)
        y = np.array(costs)
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        next_month_days = 30
        forecast = m * (len(self.historical_costs) + next_month_days) + c
        return max(0, forecast)

_cost_monitor = None
def get_cost_monitor():
    global _cost_monitor
    if _cost_monitor is None:
        _cost_monitor = CostMonitor()
    return _cost_monitor
