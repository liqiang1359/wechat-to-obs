# -*- coding: utf-8 -*-
"""本地单元测试：不依赖真实微信 / WebDAV 凭证"""

import io  # UTF-8 流
import sys  # 平台
import os  # 路径

# Windows 控制台 UTF-8
if sys.platform == "win32":
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 将项目根目录加入 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.markdown import (  # noqa: E402
  make_filename,
  build_note,
  parse_merged_chat_text,
  format_chat_lines,
)
from wechatpy.utils import check_signature  # noqa: E402
import hashlib  # noqa: E402


def test_filename():
  """测试笔记文件名格式"""
  name = make_filename("text")
  assert name.endswith("-text.md"), name
  assert len(name) == len("20260611-103000-text.md"), name
  print("✓ 文件名格式:", name)


def test_build_note():
  """测试姓名+日期+正文格式"""
  note = build_note("link", "正文内容", title="标题", author="李强")
  assert "李强" in note
  assert "正文内容" in note
  assert "标题" in note
  assert "---" not in note
  print("✓ Markdown 笔记生成通过")


def test_parse_chat():
  """测试合并聊天记录解析"""
  text = "张三 10:30\n你好\n\n李四 10:31\n收到"
  items = parse_merged_chat_text(text)
  assert len(items) == 2, items
  body = format_chat_lines(items)
  assert "**张三** 10:30" in body
  print("✓ 聊天记录解析通过")


def test_wechat_signature():
  """测试微信签名校验逻辑"""
  token = "test_token"
  timestamp = "1400000000"
  nonce = "abcdefghij"
  # 按微信规则计算签名
  sort_list = sorted([token, timestamp, nonce])
  sha1 = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
  check_signature(token, sha1, timestamp, nonce)
  print("✓ 微信签名校验通过")


def test_flask_health():
  """测试 Flask 健康检查路由（需 config.yaml 存在）"""
  config_path = os.path.join(ROOT, "config.yaml")
  if not os.path.isfile(config_path):
    print("⊘ 跳过 Flask 测试：请先复制 config.example.yaml 为 config.yaml")
    return
  from app import app, WECHAT_TOKEN  # noqa: E402
  client = app.test_client()
  resp = client.get("/health")
  assert resp.status_code == 200
  data = resp.get_json()
  assert data["status"] == "ok"
  print("✓ Flask /health 通过:", data)
  # 模拟微信 URL 验证 GET
  timestamp = "1400000000"
  nonce = "nonce_test"
  sort_list = sorted([WECHAT_TOKEN, timestamp, nonce])
  signature = hashlib.sha1("".join(sort_list).encode("utf-8")).hexdigest()
  resp2 = client.get(
    f"/wechat?signature={signature}&timestamp={timestamp}&nonce={nonce}&echostr=hello"
  )
  assert resp2.status_code == 200
  assert resp2.data.decode() == "hello"
  print("✓ 微信 URL 验证 GET 通过")


if __name__ == "__main__":
  test_filename()
  test_build_note()
  test_parse_chat()
  test_wechat_signature()
  test_flask_health()
  print("\n全部本地测试通过")
