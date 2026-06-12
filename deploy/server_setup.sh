#!/usr/bin/env bash
# 修复 root SSH 公钥权限，并部署 WechatToObs 到 /data
set -euo pipefail

# 确保 .ssh 目录存在且权限正确
mkdir -p /root/.ssh
chmod 700 /root/.ssh
chown root:root /root/.ssh

# 授权密钥（Cursor 部署用）
AUTH_KEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKpuvz4/D1GdHcRIcZwVe+iny16k5onUbF06Vlhv bill-wechat-deploy'

# 若尚未添加则写入
if ! grep -qF 'bill-wechat-deploy' /root/.ssh/authorized_keys 2>/dev/null; then
  echo "${AUTH_KEY}" >> /root/.ssh/authorized_keys
fi
chmod 600 /root/.ssh/authorized_keys
chown root:root /root/.ssh/authorized_keys

# SELinux 环境下恢复上下文
if command -v restorecon >/dev/null 2>&1; then
  restorecon -R /root/.ssh || true
fi

echo "==> SSH 公钥与权限已检查"
ls -la /root/.ssh/

# 执行主部署脚本（从 GitHub 拉取）
curl -fsSL https://raw.githubusercontent.com/liqiang1359/wechat-to-obs/main/deploy/deploy_linux.sh | bash
