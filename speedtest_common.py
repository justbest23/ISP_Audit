#!/usr/bin/env python3
"""
speedtest_common.py
Shared config, CSV helpers, and test functions used by
speedtest_light.py, speedtest_heavy.py, and speedtest_superheavy.py.
"""

import subprocess
import csv
import json
import glob
import os
from datetime import datetime

# nvm installs Node binaries (including `fast`) under a versioned path that
# cron never sees. Resolve all installed Node bin dirs and prepend to PATH.
_nvm_bins = glob.glob("/home/troggoman/.nvm/versions/node/*/bin")
if _nvm_bins:
    os.environ["PATH"] = ":".join(_nvm_bins) + ":" + os.environ.get("PATH", "")

LOG_DIR = "/home/troggoman/speedtests/logs"

CSVS = {
    "fast":        f"{LOG_DIR}/fast.csv",
    "iperf3":      f"{LOG_DIR}/iperf3.csv",
    "ndt7":        f"{LOG_DIR}/ndt7.csv",
    "ookla":       f"{LOG_DIR}/ookla.csv",
    "curl":        f"{LOG_DIR}/curl.csv",
    "ping":        f"{LOG_DIR}/ping.csv",
    "dns":         f"{LOG_DIR}/dns.csv",
}

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def ensure_csv(filename, headers):
    try:
        with open(filename, "x", newline="") as f:
            csv.writer(f).writerow(headers)
    except FileExistsError:
        pass

def init_csvs():
    ensure_csv(CSVS["fast"],   ["timestamp", "download_mbps", "upload_mbps", "latency_ms", "bufferbloat_ms", "status"])
    ensure_csv(CSVS["iperf3"], ["timestamp", "server", "download_mbps", "upload_mbps", "status"])
    ensure_csv(CSVS["ndt7"],   ["timestamp", "download_mbps", "upload_mbps", "rtt_ms", "status"])
    ensure_csv(CSVS["ookla"],  ["timestamp", "download_mbps", "upload_mbps", "ping_ms", "server_name", "server_location", "isp", "status"])
    ensure_csv(CSVS["curl"],   ["timestamp", "target_name", "region", "file_size_mb", "download_mbps", "status"])
    ensure_csv(CSVS["ping"],   ["timestamp", "host", "host_label", "avg_ms", "min_ms", "max_ms", "jitter_ms", "packet_loss_pct", "status"])
    ensure_csv(CSVS["dns"],    ["timestamp", "resolver", "lookup_ms", "status"])

def append_csv(filename, row):
    with open(filename, "a", newline="") as f:
        csv.writer(f).writerow(row)

# ---------------------------------------------------------------------------
# fast.com
# ---------------------------------------------------------------------------

def run_fast(timestamp):
    print("[fast] Starting...")
    try:
        out = subprocess.check_output(
            ["fast", "-u", "--json"],
            text=True, timeout=120
        )
        data = json.loads(out)

        def to_mbps(speed, unit):
            unit = (unit or "Mbps").strip().lower()
            return round(speed / 1000 if unit == "kbps" else float(speed), 2)

        download    = to_mbps(data.get("downloadSpeed", 0), data.get("downloadUnit", "Mbps"))
        upload      = to_mbps(data.get("uploadSpeed",   0), data.get("uploadUnit",   "Mbps"))
        latency     = data.get("latency", 0)
        bufferbloat = data.get("bufferBloat", 0)
        status      = "success"
        print(f"[fast] download={download} Mbps  upload={upload} Mbps  latency={latency} ms  bufferbloat={bufferbloat} ms")
    except subprocess.TimeoutExpired:
        print("[fast] TIMEOUT")
        download = upload = latency = bufferbloat = 0
        status = "timeout"
    except Exception as e:
        print(f"[fast] FAIL: {e}")
        download = upload = latency = bufferbloat = 0
        status = "fail"
    append_csv(CSVS["fast"], [timestamp, download, upload, latency, bufferbloat, status])

# ---------------------------------------------------------------------------
# iperf3
#
# Runs against multiple servers in priority order — local JHB servers first,
# then international. Tries each server and uses the first that succeeds.
# Both download and upload are measured (two runs per server).
# ---------------------------------------------------------------------------

IPERF3_SERVERS = [
    # (host,                        port,  label)
    ("41.168.5.158",                5201,  "JHB-Local-1"),
    ("speedtest.rocketnet.co.za",   5201,  "JHB-Rocketnet"),
    ("iperf.he.net",                5201,  "US-HE-Net"),
]

def _iperf3_run(host, port, reverse=False, timeout=60):
    """Run a single iperf3 test. Returns Mbps or None on failure."""
    cmd = ["iperf3", "-c", host, "-p", str(port), "-J", "-t", "10"]
    if reverse:
        cmd.append("-R")
    try:
        out = subprocess.check_output(cmd, text=True, timeout=timeout)
        data = json.loads(out)
        return round(data["end"]["sum_received"]["bits_per_second"] / 1_000_000, 2)
    except Exception as e:
        print(f"[iperf3]   {'upload' if reverse else 'download'} FAIL ({host}): {e}")
        return None

def run_iperf3(timestamp):
    for host, port, label in IPERF3_SERVERS:
        print(f"[iperf3] Trying {label} ({host})...")
        dl = _iperf3_run(host, port, reverse=False)
        if dl is None:
            continue
        print(f"[iperf3]   download={dl} Mbps")
        ul = _iperf3_run(host, port, reverse=True)
        if ul is None:
            ul = 0
        print(f"[iperf3]   upload={ul} Mbps")
        append_csv(CSVS["iperf3"], [timestamp, label, dl, ul, "success"])
        return
    # All servers failed
    print("[iperf3] All servers failed")
    append_csv(CSVS["iperf3"], [timestamp, "none", 0, 0, "fail"])

# ---------------------------------------------------------------------------
# ndt7
# ---------------------------------------------------------------------------

def run_ndt7(timestamp):
    print("[ndt7] Starting...")
    try:
        out = subprocess.check_output(
            ["ndt7-client", "-format", "json"],
            text=True, timeout=180
        )
        download = upload = rtt = 0

        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            value    = data.get("Value", {})
            test     = value.get("Test", "").lower()
            origin   = value.get("Origin", "")
            app_info = value.get("AppInfo", {})
            bbr_info = value.get("BBRInfo", {})

            if origin == "client" and app_info:
                elapsed = app_info.get("ElapsedTime", 0)
                nb      = app_info.get("NumBytes", 0)
                if elapsed > 0 and nb > 0:
                    mbps = round((nb * 8) / elapsed, 2)
                    if test == "download":
                        download = mbps
                    elif test == "upload":
                        upload = mbps

            if bbr_info and rtt == 0:
                min_rtt_us = bbr_info.get("MinRTT", 0)
                if min_rtt_us > 0:
                    rtt = round(min_rtt_us / 1000, 2)

        status = "success"
        print(f"[ndt7] download={download} Mbps  upload={upload} Mbps  rtt={rtt} ms")
    except subprocess.TimeoutExpired:
        print("[ndt7] TIMEOUT")
        download = upload = rtt = 0
        status = "timeout"
    except Exception as e:
        print(f"[ndt7] FAIL: {e}")
        download = upload = rtt = 0
        status = "fail"

    append_csv(CSVS["ndt7"], [timestamp, download, upload, rtt, status])

# ---------------------------------------------------------------------------
# Ookla
# ---------------------------------------------------------------------------

def run_ookla(timestamp):
    print("[ookla] Starting...")
    try:
        out = subprocess.check_output(
            ["speedtest", "-f", "json"],
            text=True, timeout=120
        )
        data            = json.loads(out)
        download        = round(data["download"]["bandwidth"] * 8 / 1_000_000, 2)
        upload          = round(data["upload"]["bandwidth"]   * 8 / 1_000_000, 2)
        ping            = data.get("ping", {}).get("latency", 0)
        server          = data.get("server", {})
        server_name     = server.get("name", "")
        server_location = server.get("location", "")
        isp             = data.get("isp", "")
        status          = "success"
        print(f"[ookla] download={download} Mbps  upload={upload} Mbps  ping={ping} ms  server={server_name}")
    except subprocess.TimeoutExpired:
        print("[ookla] TIMEOUT")
        download = upload = ping = 0
        server_name = server_location = isp = ""
        status = "timeout"
    except Exception as e:
        print(f"[ookla] FAIL: {e}")
        download = upload = ping = 0
        server_name = server_location = isp = ""
        status = "fail"

    append_csv(CSVS["ookla"], [timestamp, download, upload, ping, server_name, server_location, isp, status])

# ---------------------------------------------------------------------------
# Ping / packet loss / jitter
#
# Sends 20 pings to each host and records avg, min, max, jitter, and loss.
# Targets are chosen to test different routing paths:
#   - 1.1.1.1        Cloudflare DNS, JHB PoP — should be <10ms, tests local loop
#   - 8.8.8.8        Google DNS, nearest PoP — tests Google peering from your ISP
#   - 196.24.45.165  M-Lab JHB — same server ndt7 uses, useful cross-reference
#   - 41.168.5.158   Local JHB iperf3 server — pure domestic routing
# ---------------------------------------------------------------------------

PING_TARGETS = [
    ("1.1.1.1",       "Cloudflare-DNS-JHB"),
    ("8.8.8.8",       "Google-DNS"),
    ("196.24.45.165", "MLab-JHB"),
    ("41.168.5.158",  "JHB-Local"),
]

def run_ping_tests(timestamp):
    for host, label in PING_TARGETS:
        print(f"[ping] {label} ({host})...")
        try:
            out = subprocess.check_output(
                ["ping", "-c", "20", "-q", host],
                text=True, timeout=30
            )
            # Parse Linux ping summary:
            # "rtt min/avg/max/mdev = 4.123/5.456/8.789/1.234 ms"
            # "20 packets transmitted, 20 received, 0% packet loss"
            loss_line = [l for l in out.splitlines() if "packet loss" in l]
            rtt_line  = [l for l in out.splitlines() if "rtt min" in l or "round-trip" in l]

            loss_pct = 0.0
            if loss_line:
                import re
                m = re.search(r"(\d+(?:\.\d+)?)% packet loss", loss_line[0])
                if m:
                    loss_pct = float(m.group(1))

            avg_ms = min_ms = max_ms = jitter_ms = 0.0
            if rtt_line:
                parts = rtt_line[0].split("=")[1].strip().split("/")
                min_ms    = float(parts[0])
                avg_ms    = float(parts[1])
                max_ms    = float(parts[2])
                jitter_ms = float(parts[3].split()[0])  # mdev

            status = "success"
            print(f"[ping]   avg={avg_ms}ms  jitter={jitter_ms}ms  loss={loss_pct}%")
        except subprocess.TimeoutExpired:
            print(f"[ping]   {label} TIMEOUT")
            avg_ms = min_ms = max_ms = jitter_ms = loss_pct = 0
            status = "timeout"
        except Exception as e:
            print(f"[ping]   {label} FAIL: {e}")
            avg_ms = min_ms = max_ms = jitter_ms = loss_pct = 0
            status = "fail"

        append_csv(CSVS["ping"], [timestamp, host, label, avg_ms, min_ms, max_ms, jitter_ms, loss_pct, status])

# ---------------------------------------------------------------------------
# DNS resolution latency
#
# Times a dig query to each resolver. Tests whether your ISP's DNS is slow
# or degraded independently of throughput.
# ---------------------------------------------------------------------------

DNS_RESOLVERS = [
    ("1.1.1.1",  "Cloudflare"),
    ("8.8.8.8",  "Google"),
    ("9.9.9.9",  "Quad9"),
]
DNS_LOOKUP_HOST = "www.google.com"

def run_dns_tests(timestamp):
    for resolver, label in DNS_RESOLVERS:
        print(f"[dns] {label} ({resolver})...")
        try:
            import time
            t0  = time.monotonic()
            subprocess.check_output(
                ["dig", "+time=5", "+tries=1", f"@{resolver}", DNS_LOOKUP_HOST],
                text=True, timeout=10
            )
            elapsed_ms = round((time.monotonic() - t0) * 1000, 2)
            status = "success"
            print(f"[dns]   {label} = {elapsed_ms} ms")
        except subprocess.TimeoutExpired:
            print(f"[dns]   {label} TIMEOUT")
            elapsed_ms = 0
            status = "timeout"
        except Exception as e:
            print(f"[dns]   {label} FAIL: {e}")
            elapsed_ms = 0
            status = "fail"

        append_csv(CSVS["dns"], [timestamp, label, elapsed_ms, status])

# ---------------------------------------------------------------------------
# cURL download tests
#
# NOTHING IS SAVED TO DISK. -o /dev/null discards all bytes immediately.
# curl -w "%{speed_download}" captures average bytes/sec; ×8/1e6 = Mbps.
#
# LIGHT  — 100MB Hetzner files, 3 DCs, tests international routing paths
# HEAVY  — 1GB Hetzner + Ubuntu ISO, sustained throughput
# SUPERHEAVY — 10GB Hetzner, best-case line speed, once per day
# ---------------------------------------------------------------------------

CURL_LIGHT_TARGETS = [
    # (name,           region,          size_mb, url,                                        timeout_s)
    ("hetzner_fsn1",   "EU-Frankfurt",      100, "https://fsn1-speed.hetzner.com/100MB.bin",  60),
    ("hetzner_ash",    "US-Ashburn",        100, "https://ash-speed.hetzner.com/100MB.bin",   90),
    ("hetzner_hel1",   "EU-Helsinki",       100, "https://hel1-speed.hetzner.com/100MB.bin",  60),
]

CURL_HEAVY_TARGETS = [
    # (name,           region,          size_mb, url,                                                                      timeout_s)
    ("hetzner_fsn1",   "EU-Frankfurt",     1000, "https://fsn1-speed.hetzner.com/1GB.bin",                                  300),
    ("hetzner_ash",    "US-Ashburn",       1000, "https://ash-speed.hetzner.com/1GB.bin",                                   300),
    ("ubuntu_noble",   "Canonical-CDN",    1500, "https://releases.ubuntu.com/24.04.4/ubuntu-24.04.4-desktop-amd64.iso",   600),
]

CURL_SUPERHEAVY_TARGETS = [
    # 10GB files — Hetzner dedicated test infrastructure, no disk write
    # Two DCs for routing comparison; whichever is faster = your best-case line speed
    ("hetzner_fsn1",   "EU-Frankfurt",    10000, "https://fsn1-speed.hetzner.com/10GB.bin",   3600),
    ("hetzner_ash",    "US-Ashburn",      10000, "https://ash-speed.hetzner.com/10GB.bin",    3600),
]

def _run_curl_target(timestamp, name, region, size_mb, url, timeout_s):
    print(f"[curl] {name} ({region}, {size_mb}MB)...")
    try:
        out = subprocess.check_output(
            ["curl", "--silent", "--max-time", str(timeout_s),
             "-o", "/dev/null", "-w", "%{speed_download}", url],
            text=True, timeout=timeout_s + 10
        )
        speed_mbps = round(float(out.strip()) * 8 / 1_000_000, 2)
        status     = "success"
        print(f"[curl] {name} = {speed_mbps} Mbps")
    except subprocess.TimeoutExpired:
        print(f"[curl] {name} TIMEOUT")
        speed_mbps = 0
        status = "timeout"
    except Exception as e:
        print(f"[curl] {name} FAIL: {e}")
        speed_mbps = 0
        status = "fail"
    append_csv(CSVS["curl"], [timestamp, name, region, size_mb, speed_mbps, status])

def run_curl_light(timestamp):
    for target in CURL_LIGHT_TARGETS:
        _run_curl_target(timestamp, *target)

def run_curl_heavy(timestamp):
    for target in CURL_HEAVY_TARGETS:
        _run_curl_target(timestamp, *target)

def run_curl_superheavy(timestamp):
    for target in CURL_SUPERHEAVY_TARGETS:
        _run_curl_target(timestamp, *target)

# ---------------------------------------------------------------------------
# Eweka Usenet speed test
#
# Opens N parallel SSL NNTP connections to news.eweka.nl, authenticates,
# then downloads article bodies from a high-traffic binary group into
# /dev/null. Measures sustained real-world throughput over ~60 seconds.
#
# This is the most realistic possible download test because:
#   - It uses your actual paid Usenet account (no shared public server)
#   - Multi-connection SSL mirrors how NZBGet/SABnzbd actually downloads
#   - Eweka is in Amsterdam — tests your EU routing under real conditions
#
# Credentials are read from ~/.config/sigmon/credentials.ini:
#
#   [eweka]
#   username    = your_username
#   password    = your_password
#   server      = news.eweka.nl
#   port        = 563
#   connections = 10
#
# ---------------------------------------------------------------------------

import ssl
import socket
import threading
import time
import configparser
from pathlib import Path

CREDENTIALS_FILE = Path.home() / ".config" / "sigmon" / "credentials.ini"

def _load_eweka_config():
    """Load Eweka credentials from config file. Returns dict or None."""
    if not CREDENTIALS_FILE.exists():
        print(f"[eweka] Config file not found: {CREDENTIALS_FILE}")
        print(f"[eweka] Create it with:")
        print(f"        mkdir -p ~/.config/sigmon")
        print(f"        nano {CREDENTIALS_FILE}")
        print(f"        [eweka]")
        print(f"        username    = your_username")
        print(f"        password    = your_password")
        print(f"        server      = news.eweka.nl")
        print(f"        port        = 563")
        print(f"        connections = 10")
        return None
    cfg = configparser.ConfigParser()
    cfg.read(CREDENTIALS_FILE)
    if "eweka" not in cfg:
        print(f"[eweka] No [eweka] section in {CREDENTIALS_FILE}")
        return None
    return {
        "server":      cfg["eweka"].get("server",      "news.eweka.nl"),
        "port":        int(cfg["eweka"].get("port",    "563")),
        "username":    cfg["eweka"].get("username",    ""),
        "password":    cfg["eweka"].get("password",    ""),
        "connections": int(cfg["eweka"].get("connections", "10")),
    }

def _nntp_ssl_connect(server, port, username, password, timeout=30):
    """
    Open a raw SSL NNTP connection, authenticate, and return the socket.
    Returns None on failure.
    """
    ctx = ssl.create_default_context()
    try:
        raw = socket.create_connection((server, port), timeout=timeout)
        sock = ctx.wrap_socket(raw, server_hostname=server)
        sock.settimeout(timeout)

        def recv_line():
            buf = b""
            while not buf.endswith(b"\r\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            return buf.decode("utf-8", errors="replace").strip()

        def send(cmd):
            sock.sendall((cmd + "\r\n").encode())

        # Read greeting
        greeting = recv_line()
        if not greeting.startswith("2"):
            raise Exception(f"Bad greeting: {greeting}")

        # Auth
        send(f"AUTHINFO USER {username}")
        resp = recv_line()
        if resp.startswith("381"):
            send(f"AUTHINFO PASS {password}")
            resp = recv_line()
        if not resp.startswith("281"):
            raise Exception(f"Auth failed: {resp}")

        return sock, recv_line

    except Exception as e:
        print(f"[eweka]   connect FAIL: {e}")
        return None, None


def _worker_download(server, port, username, password, duration_s,
                     counter, counter_lock, errors, stop_event):
    """
    Single worker thread: connects, selects a group, streams article
    bodies for `duration_s` seconds, accumulates byte count in counter.
    """
    # High-volume binary group — large articles, consistently available
    GROUP = "alt.binaries.boneless"

    ctx = ssl.create_default_context()
    try:
        raw  = socket.create_connection((server, port), timeout=30)
        sock = ctx.wrap_socket(raw, server_hostname=server)
        sock.settimeout(60)
        buf  = b""

        def recv_line():
            nonlocal buf
            while b"\r\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    return ""
                buf += chunk
            line, buf = buf.split(b"\r\n", 1)
            return line.decode("utf-8", errors="replace").strip()

        def recv_body():
            """Read a multi-line NNTP body until '.\r\n', return byte count."""
            nonlocal buf
            total = 0
            while True:
                while b"\r\n" not in buf:
                    chunk = sock.recv(65536)
                    if not chunk:
                        return total
                    total += len(chunk)
                    buf += chunk
                line, buf = buf.split(b"\r\n", 1)
                if line == b".":
                    return total

        def send(cmd):
            sock.sendall((cmd + "\r\n").encode())

        # Greeting
        greeting = recv_line()
        if not greeting.startswith("2"):
            raise Exception(f"Bad greeting: {greeting}")

        # Auth
        send(f"AUTHINFO USER {username}")
        r = recv_line()
        if r.startswith("381"):
            send(f"AUTHINFO PASS {password}")
            r = recv_line()
        if not r.startswith("281"):
            raise Exception(f"Auth failed: {r}")

        # Select group
        send(f"GROUP {GROUP}")
        r = recv_line()
        if not r.startswith("211"):
            raise Exception(f"GROUP failed: {r}")

        # Parse article range: "211 count first last group"
        parts     = r.split()
        first_art = int(parts[2])
        last_art  = int(parts[3])

        # Start near the end where articles are freshest/largest
        article_id = max(first_art, last_art - 50000)

        while not stop_event.is_set():
            if article_id > last_art:
                article_id = max(first_art, last_art - 50000)

            send(f"BODY {article_id}")
            r = recv_line()
            article_id += 1

            if r.startswith("222"):
                nbytes = recv_body()
                with counter_lock:
                    counter[0] += nbytes
            elif r.startswith("423") or r.startswith("430"):
                # Article not found — skip
                continue
            else:
                # Unexpected response, small pause
                time.sleep(0.1)

    except Exception as e:
        with counter_lock:
            errors.append(str(e))
    finally:
        try:
            sock.close()
        except Exception:
            pass


def run_eweka(timestamp, duration_s=60):
    """
    Run a multi-connection Eweka Usenet speed test for `duration_s` seconds.
    Logs result to curl.csv with target_name='eweka'.
    """
    print("[eweka] Starting...")

    cfg = _load_eweka_config()
    if cfg is None:
        append_csv(CSVS["curl"], [timestamp, "eweka", "EU-Usenet", 0, 0, "config_missing"])
        return

    server  = cfg["server"]
    port    = cfg["port"]
    user    = cfg["username"]
    pw      = cfg["password"]
    n_conns = cfg["connections"]

    print(f"[eweka] {server}:{port}  connections={n_conns}  duration={duration_s}s")

    counter      = [0]          # total bytes received across all threads
    counter_lock = threading.Lock()
    errors       = []
    stop_event   = threading.Event()

    threads = []
    for i in range(n_conns):
        t = threading.Thread(
            target=_worker_download,
            args=(server, port, user, pw, duration_s,
                  counter, counter_lock, errors, stop_event),
            daemon=True,
        )
        threads.append(t)

    t_start = time.monotonic()
    for t in threads:
        t.start()

    time.sleep(duration_s)
    stop_event.set()

    for t in threads:
        t.join(timeout=15)

    elapsed  = time.monotonic() - t_start
    total_mb = counter[0] / (1024 * 1024)
    speed_mbps = round((counter[0] * 8) / (elapsed * 1_000_000), 2)

    if errors:
        unique_errors = list(set(errors))
        print(f"[eweka] {len(errors)} thread error(s): {unique_errors[:3]}")

    if speed_mbps > 0:
        status = "success"
        print(f"[eweka] {total_mb:.1f} MB in {elapsed:.1f}s = {speed_mbps} Mbps")
    else:
        status = "fail"
        print(f"[eweka] FAIL — 0 bytes received")

    # Size logged as approximate MB transferred (varies each run)
    append_csv(CSVS["curl"], [timestamp, "eweka", "EU-Usenet", round(total_mb), speed_mbps, status])