# -*- coding: utf-8 -*-
"""自动将本地改动提交并推送到 GitHub（变更检测 + 定时兜底）"""

import argparse  # 命令行参数
import io  # UTF-8 标准流
import os  # 路径与环境
import subprocess  # 执行 git 命令
import sys  # 平台判断
import time  # 轮询与休眠
from datetime import datetime  # 提交时间戳

# Windows 控制台 UTF-8 输出
if sys.platform == "win32":
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 项目根目录（scripts 的上一级）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 同步日志文件路径
LOG_FILE = os.path.join(ROOT, "scripts", "auto_sync.log")


def log(message: str) -> None:
  """写入带时间戳的日志（同时打印到控制台）"""
  line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
  print(line, flush=True)
  try:
    with open(LOG_FILE, "a", encoding="utf-8") as fp:
      fp.write(line + "\n")
  except OSError:
    pass


def run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
  """在仓库根目录执行 git 子命令"""
  cmd = ["git", *args]
  return subprocess.run(
    cmd,
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    check=check,
  )


def has_changes() -> bool:
  """检查工作区是否有未提交改动"""
  result = run_git(["status", "--porcelain"], check=False)
  return bool(result.stdout.strip())


def sync_once() -> bool:
  """若有改动则 add / commit / push，返回是否执行了推送"""
  if not has_changes():
    return False

  status = run_git(["status", "--short"], check=False)
  log("检测到改动，开始同步…")
  log(status.stdout.strip() or "(无详情)")

  run_git(["add", "-A"], check=True)

  if not has_changes():
    log("add 后无有效改动，跳过提交")
    return False

  msg = f"auto: 自动同步 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
  commit = run_git(["commit", "-m", msg], check=False)
  if commit.returncode != 0:
    log(f"提交失败: {commit.stderr.strip()}")
    return False

  push = run_git(["push", "origin", "HEAD"], check=False)
  if push.returncode != 0:
    log(f"推送失败: {push.stderr.strip()}")
    return False

  log("已推送到 GitHub")
  return True


def ensure_git_repo() -> None:
  """确认当前目录是已配置远程的 git 仓库"""
  if not os.path.isdir(os.path.join(ROOT, ".git")):
    raise SystemExit(f"未找到 git 仓库: {ROOT}")

  remote = run_git(["remote", "get-url", "origin"], check=False)
  if remote.returncode != 0:
    raise SystemExit("未配置 origin 远程，请先关联 GitHub 仓库")


def run_watch_mode(poll_sec: int, debounce_sec: int, max_interval_sec: int) -> None:
  """变更检测模式：轮询 + 防抖，并定时兜底同步"""
  log(
    f"监听模式启动：轮询 {poll_sec}s，防抖 {debounce_sec}s，"
    f"最长间隔 {max_interval_sec}s"
  )
  dirty_since: float | None = None
  last_sync_at = time.monotonic()

  while True:
    now = time.monotonic()

    if has_changes():
      if dirty_since is None:
        dirty_since = now
      stable_for = now - dirty_since
      due_by_debounce = stable_for >= debounce_sec
      due_by_interval = (now - last_sync_at) >= max_interval_sec

      if due_by_debounce or due_by_interval:
        if sync_once():
          last_sync_at = time.monotonic()
        dirty_since = None
    else:
      dirty_since = None

    time.sleep(poll_sec)


def run_interval_mode(interval_sec: int) -> None:
  """纯定时模式：每隔固定秒数检查并同步"""
  log(f"定时模式启动：每 {interval_sec}s 检查一次")
  while True:
    sync_once()
    time.sleep(interval_sec)


def main() -> None:
  """解析参数并启动自动同步"""
  parser = argparse.ArgumentParser(description="自动同步 wechat-to-obs 到 GitHub")
  parser.add_argument(
    "--mode",
    choices=["watch", "interval"],
    default="watch",
    help="watch=有变动尽快推送；interval=仅按固定间隔检查",
  )
  parser.add_argument(
    "--interval",
    type=int,
    default=180,
    help="定时间隔或监听兜底间隔（秒），建议 120~300，默认 180",
  )
  parser.add_argument(
    "--poll",
    type=int,
    default=10,
    help="监听模式下轮询间隔（秒），默认 10",
  )
  parser.add_argument(
    "--debounce",
    type=int,
    default=5,
    help="监听模式下改动稳定多久后推送（秒），默认 5",
  )
  parser.add_argument(
    "--once",
    action="store_true",
    help="只执行一次同步后退出（供计划任务调用）",
  )
  args = parser.parse_args()

  ensure_git_repo()

  if args.once:
    sync_once()
    return

  if args.mode == "interval":
    run_interval_mode(max(60, args.interval))
  else:
    run_watch_mode(
      poll_sec=max(3, args.poll),
      debounce_sec=max(2, args.debounce),
      max_interval_sec=max(60, args.interval),
    )


if __name__ == "__main__":
  main()
