# -*- coding: utf-8 -*-
"""通过 SSH 在 Linux 服务器部署 WechatToObs"""

import io  # UTF-8 流
import sys  # 平台与退出码
import time  # 等待服务启动

if sys.platform == "win32":
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import paramiko  # SSH 客户端

# 服务器地址
HOST = "192.168.99.211"
# SSH 用户
USER = "root"
# 私钥路径
KEY_PATH = r"C:\Users\Bill\.ssh\id_ed25519_wechat"
# 一键部署命令
DEPLOY_CMD = (
  "curl -fsSL https://raw.githubusercontent.com/liqiang1359/wechat-to-obs/main/deploy/deploy_linux.sh | bash"
)
# 部署后验证命令
VERIFY_CMD = (
  "echo '--- local health ---'; "
  "curl -s http://127.0.0.1:5000/health; echo; "
  "echo '--- remote health ---'; "
  "curl -s https://wechat.nobbn.com/health; echo; "
  "echo '--- service ---'; "
  "systemctl is-active wechat-obs cloudflared; "
  "ls -la /data/wechat-to-obs/config.yaml 2>/dev/null || echo 'no config.yaml'"
)


def run_remote(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
  """执行远程命令并返回退出码与输出"""
  client = paramiko.SSHClient()
  client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
  key = paramiko.Ed25519Key.from_private_key_file(KEY_PATH)
  client.connect(HOST, username=USER, pkey=key, timeout=20)
  try:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return exit_code, out, err
  finally:
    client.close()


def main() -> None:
  """连接服务器、部署并验证"""
  print(f"连接 {USER}@{HOST} ...")
  code, out, err = run_remote(DEPLOY_CMD, timeout=600)
  print(out)
  if err:
    print(err)
  if code != 0:
    print(f"部署脚本退出码: {code}")
    sys.exit(code)

  time.sleep(2)
  print("\n验证中...")
  code, out, err = run_remote(VERIFY_CMD, timeout=60)
  print(out)
  if err:
    print(err)
  sys.exit(code)


if __name__ == "__main__":
  main()
