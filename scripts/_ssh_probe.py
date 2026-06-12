# -*- coding: utf-8 -*-
"""临时 SSH 探测脚本"""

import io  # UTF-8
import sys  # 平台

if sys.platform == "win32":
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import paramiko  # SSH 客户端

HOST = "192.168.99.211"
USER = "root"
CMD = (
  "hostname; uname -a; ls -la /data; "
  "ss -tlnp | grep 5000 || true; "
  "systemctl is-active wechat-obs cloudflared 2>/dev/null || true; "
  "ps aux | grep python | grep -v grep || true"
)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

for label, kwargs in [
  ("key/agent", {"allow_agent": True, "look_for_keys": True}),
  ("password", {"password": "123.abc", "allow_agent": False, "look_for_keys": False}),
]:
  try:
    client.connect(HOST, username=USER, timeout=12, **kwargs)
    print(f"CONNECTED via {label}")
    _, stdout, stderr = client.exec_command(CMD)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
      print("STDERR:", err)
    client.close()
    sys.exit(0)
  except Exception as exc:
    print(f"FAIL {label}: {exc}")

sys.exit(1)
