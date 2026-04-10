#!/usr/bin/env bash
set -e

echo "[*] Updating package lists..."
sudo apt-get update -y

echo "[*] Installing base tools (curl, iperf3, node, npm, python3-pip)..."
sudo apt-get install -y curl iperf3 nodejs npm python3-pip

# --- Ookla Speedtest CLI ---
if ! command -v speedtest >/dev/null 2>&1; then
  echo "[*] Installing Ookla Speedtest CLI..."
  curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
  sudo apt-get install -y speedtest
else
  echo "[✓] Ookla Speedtest already installed"
fi

# --- Fast.com CLI ---
if ! command -v fast >/dev/null 2>&1; then
  echo "[*] Installing fast-cli (npm)..."
  sudo npm install -g fast-cli
else
  echo "[✓] fast-cli already installed"
fi

# --- NDT7 (Measurement Lab) ---
if ! command -v ndt7-client >/dev/null 2>&1; then
  echo "[*] Installing ndt7-client..."
  go install github.com/m-lab/ndt7-client-go/cmd/ndt7-client@latest
  sudo mv ~/go/bin/ndt7-client /usr/local/bin/
else
  echo "[✓] ndt7-client already installed"
fi

# --- LibreSpeed CLI ---
if ! command -v librespeed-cli >/dev/null 2>&1; then
  echo "[*] Installing librespeed-cli..."
  wget -qO /tmp/librespeed.tar.gz https://github.com/librespeed/speedtest-cli/releases/latest/download/librespeed-cli_$(uname -m)_linux.tar.gz
  tar -xzf /tmp/librespeed.tar.gz -C /tmp
  sudo mv /tmp/librespeed-cli /usr/local/bin/
  rm -f /tmp/librespeed.tar.gz
else
  echo "[✓] librespeed-cli already installed"
fi

echo "[*] All prerequisites installed!"
