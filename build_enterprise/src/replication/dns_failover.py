# replication/dns_failover.py – Update DNS records on failover
import os
import json
import requests
from typing import Dict

class DNSManager:
    def __init__(self, provider: str = "route53"):
        self.provider = provider
        self.config = self._load_config()
    
    def _load_config(self):
        default = {
            "route53": {"zone_id": "", "record_name": "api.crownstar.ai", "ttl": 60},
            "cloudflare": {"zone_id": "", "record_name": "api.crownstar.ai", "api_token": ""},
            "azure_traffic_manager": {"profile_name": "crownstar-tm", "resource_group": "crownstar"}
        }
        if os.path.exists("config/replication/dns.json"):
            with open("config/replication/dns.json", "r") as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def update_record(self, ip_or_hostname: str, region: str):
        if self.provider == "route53":
            return self._update_route53(ip_or_hostname, region)
        elif self.provider == "cloudflare":
            return self._update_cloudflare(ip_or_hostname, region)
        elif self.provider == "azure_traffic_manager":
            return self._update_azure(ip_or_hostname, region)
        else:
            print(f"No DNS update for provider {self.provider}")
            return False
    
    def _update_route53(self, ip: str, region: str):
        # Placeholder – would use boto3
        print(f"Route53: updating {self.config['route53']['record_name']} to {ip}")
        return True
    
    def _update_cloudflare(self, ip: str, region: str):
        zone_id = self.config["cloudflare"]["zone_id"]
        record_name = self.config["cloudflare"]["record_name"]
        token = self.config["cloudflare"]["api_token"]
        # Find existing record
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.get(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={record_name}", headers=headers)
        if resp.status_code == 200:
            records = resp.json().get("result", [])
            for rec in records:
                if rec["type"] == "A":
                    update_data = {"type": "A", "name": record_name, "content": ip, "ttl": 60}
                    requests.put(f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{rec['id']}", json=update_data, headers=headers)
        return True
    
    def _update_azure(self, ip: str, region: str):
        # Placeholder – would use Azure SDK
        print(f"Azure Traffic Manager: updating endpoint for region {region}")
        return True

_dns = None
def get_dns_manager():
    global _dns
    if _dns is None:
        _dns = DNSManager()
    return _dns
