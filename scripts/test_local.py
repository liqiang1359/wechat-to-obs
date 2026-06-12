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
  normalize_wechat_paste,
  parse_wechat_shared_link,
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
  """测试不添加微信用户行，并整理微信复制格式"""
  paste = "徐行\n2026年06月12日 11:13\n但是我开了20X的codex"
  note = build_note("text", paste)
  assert "微信用户" not in note
  assert note.startswith("徐行    2026年06月12日 11:13")
  assert "但是我开了20X的codex" in note
  link_note = build_note("link", "正文内容", title="标题")
  assert "标题" in link_note
  assert "正文内容" in link_note
  assert "---" not in link_note
  print("✓ Markdown 笔记生成通过")


def test_parse_wechat_shared_link():
  """测试微信 [链接] 转发格式解析"""
  raw = (
    "无水的鱼    2026年06月12日 14:41\n"
    "[链接] 化繁为简-AIMIX智剪 V1.4.7 产品功能更新\n"
    "https://mp.weixin.qq.com/s?__biz=MzkyMDYxODU0NQ==&mid=2247484107"
  )
  info = parse_wechat_shared_link(raw)
  assert info is not None, info
  assert info["header"] == "无水的鱼    2026年06月12日 14:41"
  assert "AIMIX" in info["title"]
  assert info["url"].startswith("https://mp.weixin.qq.com/")
  plain = "你好世界"
  assert parse_wechat_shared_link(plain) is None
  print("✓ [链接] 转发解析通过")


def test_normalize_wechat_paste():
  """测试微信三行复制格式整理为两行"""
  raw = "D\n2026年06月12日 11:13\n价格如何"
  out = normalize_wechat_paste(raw)
  assert out == "D    2026年06月12日 11:13\n价格如何", out
  print("✓ 微信复制格式整理通过")


def test_parse_chat():
  """测试合并聊天记录解析"""
  text = "张三 10:30\n你好\n\n李四 10:31\n收到"
  items = parse_merged_chat_text(text)
  assert len(items) == 2, items
  body = format_chat_lines(items)
  assert "张三    10:30" in body
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
  test_normalize_wechat_paste()
  test_parse_wechat_shared_link()
  test_parse_chat()
  test_wechat_signature()
  test_flask_health()
  print("\n全部本地测试通过")
