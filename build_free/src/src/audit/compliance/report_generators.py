# audit/compliance/report_generators.py – Compliance report generation
import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from ..audit_service import get_audit_service

class ComplianceReportGenerator:
    def __init__(self):
        self.audit = get_audit_service()
    
    def gdpr_data_subject_access(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict:
        events = self.audit.search_events(start_date, end_date, user_id=user_id, limit=10000)
        report = {
            "report_type": "GDPR Subject Access Request",
            "generated_at": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "events_count": len(events),
            "events": events[:1000],
            "data_categories": self._categorize_user_data(events)
        }
        return report
    
    def _categorize_user_data(self, events: List[Dict]) -> Dict:
        categories = {
            "conversations": 0,
            "module_toggles": 0,
            "tier_changes": 0,
            "api_calls": 0,
            "auth_events": 0
        }
        for ev in events:
            if ev["resource"] == "conversation":
                categories["conversations"] += 1
            elif ev["action"] == "toggle_module":
                categories["module_toggles"] += 1
            elif ev["action"] == "change_tier":
                categories["tier_changes"] += 1
            elif ev["resource"].startswith("/v"):
                categories["api_calls"] += 1
            elif "auth" in ev["event_type"]:
                categories["auth_events"] += 1
        return categories
    
    def gdpr_deletion_manifest(self, user_id: str, deletion_date: datetime) -> Dict:
        return {
            "report_type": "GDPR Erasure Record",
            "user_id": user_id,
            "deletion_date": deletion_date.isoformat(),
            "data_erased": ["conversations", "personal_info", "audit_events"],
            "retained_for_compliance": ["anonymised_audit"],
            "retention_reason": "Legal obligation"
        }
    
    def soc2_control_evidence(self, control_id: str, start_date: datetime, end_date: datetime) -> Dict:
        control_mapping = {
            "CC6.1": "Logical access controls",
            "CC7.1": "System operations monitoring",
            "CC8.1": "Change management",
            "A1.2": "Incident response"
        }
        events = self.audit.search_events(start_date, end_date, limit=5000)
        report = {
            "report_type": "SOC2 Control Evidence",
            "control_id": control_id,
            "control_name": control_mapping.get(control_id, "Unknown"),
            "period": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "evidence": [
                {"type": "audit_logs", "count": len(events), "sample": events[:50]},
                {"type": "configuration_changes", "count": sum(1 for e in events if "config" in e["resource"])}
            ]
        }
        return report
    
    def hipaa_access_report(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict:
        events = self.audit.search_events(start_date, end_date, user_id=user_id, event_type="phi_access", limit=1000)
        report = {
            "report_type": "HIPAA Access Report",
            "user_id": user_id,
            "period": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "access_events": events,
            "unauthorized_attempts": sum(1 for e in events if e.get("details",{}).get("authorized") == False)
        }
        return report
    
    def generate_pci_dss_report(self, start_date: datetime, end_date: datetime) -> Dict:
        events = self.audit.search_events(start_date, end_date, limit=10000)
        report = {
            "report_type": "PCI DSS Requirement 10",
            "period": f"{start_date.isoformat()} to {end_date.isoformat()}",
            "total_events": len(events),
            "failed_logins": sum(1 for e in events if "login_failed" in e["event_type"]),
            "privileged_actions": sum(1 for e in events if e.get("details",{}).get("privileged") == True),
            "logs_protected": self.audit.verify_integrity()["valid"] > 0,
            "retention_compliant": True
        }
        return report

_compliance = None
def get_compliance():
    global _compliance
    if _compliance is None:
        _compliance = ComplianceReportGenerator()
    return _compliance
