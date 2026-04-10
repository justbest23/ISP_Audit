#!/usr/bin/env python3
"""
speedtest_heavy.py
Heavy download tests — intended to run 4 times per day via cron.

Runs: curl (1GB Hetzner Frankfurt, 1GB Hetzner Ashburn, ~1.5GB Ubuntu ISO)
Typical runtime: 10–30 minutes depending on your line speed.

NOTHING IS SAVED TO DISK — all downloads go straight to /dev/null.

Cron example (4× per day at 02:00, 08:00, 14:00, 20:00):
  0 2,8,14,20 * * * /usr/bin/python3 /home/troggoman/speedtests/speedtest_heavy.py >> /home/troggoman/speedtests/logs/heavy.log 2>&1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from speedtest_common import *
from datetime import datetime

if __name__ == "__main__":
    timestamp = datetime.now().isoformat()
    print(f"=== [HEAVY] Speedtest run: {timestamp} ===")
    init_csvs()
    run_curl_heavy(timestamp)
    print("=== [HEAVY] Done ===")
