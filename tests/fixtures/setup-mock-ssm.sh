#!/usr/bin/env bash
# Start a local HTTPS mock of the AWS SSM endpoint and redirect the regional
# SSM hostname to it via /etc/hosts. Requests are logged to
# /tmp/mock-ssm/requests.log (one JSON line per request).
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
HOST="ssm.${REGION}.amazonaws.com"
DIR=/tmp/mock-ssm
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

SUDO=""
if [ "$(id -u)" != "0" ]; then SUDO="sudo"; fi

$SUDO mkdir -p "$DIR"
$SUDO chmod 777 "$DIR"
: > "$DIR/requests.log"
chmod 666 "$DIR/requests.log" || true

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$DIR/key.pem" -out "$DIR/cert.pem" -days 1 \
  -subj "/CN=$HOST" -addext "subjectAltName=DNS:$HOST" >/dev/null 2>&1

echo "127.0.0.1 $HOST" | $SUDO tee -a /etc/hosts >/dev/null

$SUDO setsid nohup python3 "$SCRIPT_DIR/mock_ssm.py" \
  "$DIR/cert.pem" "$DIR/key.pem" "$DIR/requests.log" \
  > "$DIR/server.out" 2>&1 < /dev/null &

for i in $(seq 1 50); do
  if python3 -c "import socket; socket.create_connection(('127.0.0.1', 443), 1).close()" 2>/dev/null; then
    echo "Mock SSM listening for $HOST"
    getent hosts "$HOST" || true
    exit 0
  fi
  sleep 0.2
done
echo "Mock SSM server failed to start"
cat "$DIR/server.out" || true
exit 1
