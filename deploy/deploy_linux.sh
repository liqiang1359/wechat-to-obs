#!/usr/bin/env bash
# 在 Linux 服务器 /data 目录部署 WechatToObs
set -euo pipefail

# 安装目标目录
INSTALL_DIR="/data/wechat-to-obs"
# GitHub 仓库地址
REPO_URL="https://github.com/liqiang1359/wechat-to-obs.git"
# 服务名
SERVICE_NAME="wechat-obs"

echo "==> 部署目录: ${INSTALL_DIR}"

# 安装系统依赖（git、python3、venv）
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq git python3 python3-venv python3-pip curl
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y git python3 python3-pip curl
elif command -v yum >/dev/null 2>&1; then
  yum install -y git python3 python3-pip curl
fi

# 停止占用 5000 端口的旧进程（含临时测试 HTTP 服务）
if ss -tlnp 2>/dev/null | grep -q ':5000'; then
  echo "==> 释放 5000 端口..."
  fuser -k 5000/tcp 2>/dev/null || true
  sleep 1
fi

# 拉取或更新代码
if [ -d "${INSTALL_DIR}/.git" ]; then
  echo "==> 更新代码..."
  git -C "${INSTALL_DIR}" pull --ff-only
else
  echo "==> 克隆仓库..."
  mkdir -p /data
  git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"

# Python 虚拟环境与依赖
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

# 配置文件（不覆盖已有 config.yaml）
if [ ! -f config.yaml ]; then
  cp config.example.yaml config.yaml
  chmod 600 config.yaml
  echo "!! 已生成 config.yaml，请编辑微信与 WebDAV 凭证后重启服务"
fi

# 确保监听本机（配合 Cloudflare Tunnel）
python3 - <<'PY'
import pathlib
import re

path = pathlib.Path("config.yaml")
text = path.read_text(encoding="utf-8")
if re.search(r"host:\s*0\.0\.0\.0", text):
  text = re.sub(r"host:\s*0\.0\.0\.0", "host: 127.0.0.1", text)
  path.write_text(text, encoding="utf-8")
  print("==> 已将 server.host 改为 127.0.0.1")
PY

# 安装 systemd 服务
cp deploy/wechat-obs.service "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

sleep 2

echo "==> 服务状态:"
systemctl --no-pager status "${SERVICE_NAME}" || true

echo "==> 本机健康检查:"
curl -s http://127.0.0.1:5000/health || true
echo ""

echo "==> 外网健康检查（若已配置 Tunnel）:"
curl -s https://wechat.nobbn.com/health || true
echo ""

echo "完成。若外网仍 502，请在 Cloudflare Zero Trust 将源站改为 http://127.0.0.1:5000（不要用 https）"
