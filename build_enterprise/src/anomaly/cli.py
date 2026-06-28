#!/usr/bin/env python3
# anomaly/cli.py – Standalone CLI for anomaly detection (for cron)
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from anomaly.monitoring_daemon import get_monitoring_daemon

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Run one anomaly check cycle")
    args = parser.parse_args()
    if args.check:
        daemon = get_monitoring_daemon()
        daemon._collect_metrics()  # one shot
        print("Anomaly check completed")
    else:
        daemon = get_monitoring_daemon()
        daemon.start()
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            daemon.stop()

if __name__ == "__main__":
    main()
