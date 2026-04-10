#!/usr/bin/env python3
"""
speedtest_light.py
Lightweight tests — intended to run every 20 minutes via cron.

Runs: ookla, fast, iperf3, ndt7, curl (3× Hetzner 100MB), ping (4 hosts), DNS (3 resolvers)
Typical runtime: 6–10 minutes

Cron example (every 20 min):
  */20 * * * * /usr/bin/python3 /home/troggoman/speedtests/speedtest_light.py >> /home/troggoman/speedtests/logs/light.log 2>&1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from speedtest_common import *
from datetime import datetime

if __name__ == "__main__":
    timestamp = datetime.now().isoformat()
    print(f"=== [LIGHT] Speedtest run: {timestamp} ===")
    init_csvs()
    run_ookla(timestamp)
    run_fast(timestamp)
    run_iperf3(timestamp)
    run_ndt7(timestamp)
    run_curl_light(timestamp)
    run_ping_tests(timestamp)
    run_mtr_tests(timestamp)
    run_dns_tests(timestamp)
    print("=== [LIGHT] Done ===")
