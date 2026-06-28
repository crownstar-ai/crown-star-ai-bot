# scaling/cost/spot_handler.py – Handle spot instance termination notices
import os
import signal
import sys
import time
import json
import threading
from datetime import datetime
from typing import Optional
import requests

class SpotInterruptionHandler:
    def __init__(self, checkpoint_dir: str = "data/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
        self.interruption_notified = False
        self.interruption_time = None
        self._hook_installed = False
    
    def install_handlers(self):
        """Install signal handlers and metadata endpoint watcher for AWS/Azure/GCP"""
        # AWS IMDS (Instance Metadata Service)
        signal.signal(signal.SIGTERM, self._handle_termination)
        signal.signal(signal.SIGINT, self._handle_termination)
        # Start polling for spot interruption notices
        self._start_aws_imds_poller()
        self._start_azure_scheduled_events_poller()
        self._start_gcp_preemption_poller()
        self._hook_installed = True
        print("Spot interruption handlers installed")
    
    def _handle_termination(self, signum, frame):
        print(f"Received termination signal {signum}. Starting graceful shutdown...")
        self.interruption_notified = True
        self.interruption_time = datetime.utcnow()
        self._save_checkpoint()
        # Notify CrownStar core to save state
        self._notify_crownstar_save()
        sys.exit(0)
    
    def _save_checkpoint(self):
        checkpoint = {
            "timestamp": self.interruption_time.isoformat(),
            "interruption_type": "spot_termination",
            "handled": True
        }
        with open(os.path.join(self.checkpoint_dir, "spot_checkpoint.json"), "w") as f:
            json.dump(checkpoint, f, indent=2)
        print(f"Checkpoint saved to {self.checkpoint_dir}")
    
    def _notify_crownstar_save(self):
        """Call CrownStar API to save memory and conversation state"""
        try:
            requests.post("http://localhost:8080/v1/internal/save_state", timeout=5)
        except:
            pass
    
    def _start_aws_imds_poller(self):
        def poll_aws():
            while not self.interruption_notified:
                try:
                    # AWS IMDSv2 token
                    token_resp = requests.put("http://169.254.169.254/latest/api/token", headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"}, timeout=1)
                    if token_resp.status_code == 200:
                        token = token_resp.text
                        headers = {"X-aws-ec2-metadata-token": token}
                        resp = requests.get("http://169.254.169.254/latest/meta-data/spot/termination-time", headers=headers, timeout=1)
                        if resp.status_code == 200:
                            termination_time = resp.text
                            print(f"AWS spot termination notice received: {termination_time}")
                            self._handle_termination(None, None)
                except:
                    pass
                time.sleep(2)
        threading.Thread(target=poll_aws, daemon=True).start()
    
    def _start_azure_scheduled_events_poller(self):
        def poll_azure():
            while not self.interruption_notified:
                try:
                    resp = requests.get("http://169.254.169.254/metadata/scheduledevents?api-version=2020-07-01", headers={"Metadata": "true"}, timeout=1)
                    if resp.status_code == 200:
                        events = resp.json().get("Events", [])
                        for event in events:
                            if event.get("EventType") in ["Preempt", "Terminate"]:
                                print(f"Azure scheduled event: {event}")
                                self._handle_termination(None, None)
                except:
                    pass
                time.sleep(2)
        threading.Thread(target=poll_azure, daemon=True).start()
    
    def _start_gcp_preemption_poller(self):
        def poll_gcp():
            while not self.interruption_notified:
                try:
                    # GCP sends a SIGTERM 30 seconds before preemption – we already catch signal
                    # Additionally check metadata
                    resp = requests.get("http://metadata.google.internal/computeMetadata/v1/instance/preempted", headers={"Metadata-Flavor": "Google"}, timeout=1)
                    if resp.status_code == 200 and resp.text == "TRUE":
                        print("GCP preemption notice received")
                        self._handle_termination(None, None)
                except:
                    pass
                time.sleep(5)
        threading.Thread(target=poll_gcp, daemon=True).start()
    
    def is_interrupted(self) -> bool:
        return self.interruption_notified

# Global instance
_spot_handler = None
def get_spot_handler():
    global _spot_handler
    if _spot_handler is None:
        _spot_handler = SpotInterruptionHandler()
    return _spot_handler
