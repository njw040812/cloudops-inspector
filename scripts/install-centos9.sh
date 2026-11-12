#!/usr/bin/env bash
# One-shot installer for a CentOS Stream 9 Docker host.
# Run as root from the repository root:
#   bash scripts/install-centos9.sh
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

PROJECT_DIR="${PROJECT_DIR:-/opt/cloudops-inspector}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
API_HOST="${API_HOST:-}"
if [[ -z "${API_HOST}" ]]; then
  if command -v docker >/dev/null 2>&1 && ip -4 addr show docker0 2>/dev/null | grep -q 'inet 172\.17\.0\.1/'; then
    API_HOST="172.17.0.1"
  else
    API_HOST="127.0.0.1"
  fi
fi

if [[ ! -f "${PROJECT_DIR}/pyproject.toml" ]]; then
  echo "project not found at ${PROJECT_DIR}" >&2
  echo "clone first: git clone https://github.com/njw040812/cloudops-inspector.git ${PROJECT_DIR}" >&2
  exit 1
fi

cd "${PROJECT_DIR}"

echo "==> create virtualenv"
python3 -m venv .venv

echo "==> install runtime dependencies"
.venv/bin/pip install --disable-pip-version-check -q -i "${PIP_INDEX_URL}" -r requirements.txt

echo "==> create config directories"
install -d -m 0755 /etc/cloudops
install -d -m 0755 /var/lib/cloudops/reports

if [[ ! -f /etc/cloudops/inventory.yml ]]; then
  cp examples/inventory.local.yml /etc/cloudops/inventory.yml
fi
if [[ ! -f /etc/cloudops/rules.yml ]]; then
  cp rules/default.yml /etc/cloudops/rules.yml
fi

echo "==> run first inspection"
set +e
.venv/bin/python -m cloudops_inspector inspect \
  --inventory /etc/cloudops/inventory.yml \
  --rules /etc/cloudops/rules.yml \
  --db /var/lib/cloudops/inspector.db \
  --output /var/lib/cloudops/reports
inspect_code=$?
set -e

echo "==> install systemd units"
sed "s#/opt/cloudops-inspector#${PROJECT_DIR}#g" systemd/cloudops-inspector.service \
  > /etc/systemd/system/cloudops-inspector.service
sed "s#/opt/cloudops-inspector#${PROJECT_DIR}#g" systemd/cloudops-inspector-api.service \
  | sed "s#--host 127.0.0.1#--host ${API_HOST}#g" \
  > /etc/systemd/system/cloudops-inspector-api.service
cp systemd/cloudops-inspector.timer /etc/systemd/system/cloudops-inspector.timer
systemctl daemon-reload
systemctl enable --now cloudops-inspector.timer
systemctl enable --now cloudops-inspector-api.service

echo "==> latest report"
ls -1t /var/lib/cloudops/reports/*.html 2>/dev/null | head -1 || true

echo "inspection exit code: ${inspect_code} (1 means warnings/critical findings, not a crash)"
echo "timer: $(systemctl is-enabled cloudops-inspector.timer 2>/dev/null || true)"
echo "api: $(systemctl is-active cloudops-inspector-api.service 2>/dev/null || true) (${API_HOST}:8000)"
