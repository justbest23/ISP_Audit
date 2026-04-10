#!/usr/bin/env python3
"""
speedtest_superheavy.py
10GB sustained download test — run once per day via cron.

Downloads 10GB from two Hetzner datacenters (Frankfurt + Ashburn) to /dev/null.
Nothing is written to disk. The result is the best sustained throughput your
line can achieve over a long enough transfer to fully exit TCP slow-start.

Results land in the same curl.csv as light/heavy tests, tagged with
target_name=hetzner_fsn1/hetzner_ash and file_size_mb=10000.

Cron example (once daily at 03:00):
  0 3 * * * /usr/bin/python3 /home/troggoman/speedtests/speedtest_superheavy.py >> /home/troggoman/speedtests/logs/superheavy.log 2>&1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from speedtest_common import *
from datetime import datetime

if __name__ == "__main__":
    timestamp = datetime.now().isoformat()
    print(f"=== [SUPERHEAVY] Speedtest run: {timestamp} ===")
    print("    10GB × 2 targets — this will take a while")
    init_csvs()
    run_curl_superheavy(timestamp)
    print("=== [SUPERHEAVY] Done ===")
