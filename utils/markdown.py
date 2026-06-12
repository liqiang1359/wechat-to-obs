# -*- coding: utf-8 -*-
"""Markdown 笔记生成模块"""

import re  # 正则解析聊天记录
from datetime import datetime  # 时间戳与文件名

# 微信复制/转发常见的日期行（中文或 ISO 格式）
_WECHAT_DATE_LINE_RE = re.compile(
  r"^(\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2})"
  r"|^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?)$"
)
# 微信转发链接/图片标记与 URL 提取
_LINK_MARKER_RE = re.compile(r"\[链接\]")
_IMAGE_MARKER_RE = re.compile(r"\[图片\]")
_URL_RE = re.compile(r"https?://[^\s\]\)】]+")


def make_filename(msg_type, dt=None):
  """
  生成 Obsidian 笔记文件名：YYYYMMDD-HHMMSS-类型.md
  :param msg_type: 消息类型 text/link/image/file/chat/note
  :param dt: 可选 datetime，默认当前时间
  :return: 文件名字符串
  """
  when = dt or datetime.now()
  time_part = when.strftime("%Y%m%d-%H%M%S")
  return f"{time_part}-{msg_type}.md"


def normalize_wechat_paste(body):
  """
  整理微信复制/转发的多行格式为「姓名    日期\\n正文」
  不添加「微信用户 + 服务器收到时间」行
  :param body: 原始消息正文
  :return: 整理后的文本
  """
  text = (body or "").strip()
  if not text:
    return ""
  lines = [ln.rstrip() for ln in text.split("\n")]
  # 至少三行：姓名、日期、正文
  if len(lines) >= 3:
    name = lines[0].strip()
    date_line = lines[1].strip()
    if name and _WECHAT_DATE_LINE_RE.match(date_line):
      content = "\n".join(lines[2:]).strip()
      header = f"{name}    {date_line}"
      return f"{header}\n{content}" if content else header
  return text


def parse_wechat_shared_image(text):
  """
  解析微信转发的 [图片] 纯文本格式
  :param text: 原始消息正文
  :return: {"title", "url", "header"} 或 None
  """
  raw = (text or "").strip()
  if not raw or not _IMAGE_MARKER_RE.search(raw):
    return None
  url_match = _URL_RE.search(raw)
  if not url_match:
    return None
  url = url_match.group(0).rstrip(".,;)")
  title = ""
  header = None
  for line in raw.split("\n"):
    stripped = line.strip()
    if not stripped:
      continue
    if stripped.startswith("http://") or stripped.startswith("https://"):
      continue
    if _IMAGE_MARKER_RE.search(stripped):
      title = _IMAGE_MARKER_RE.sub("", stripped).strip()
      continue
    if header is None:
      header = stripped
  if not title:
    title = "图片"
  return {"title": title, "url": url, "header": header}


def parse_wechat_shared_link(text):
  """
  解析微信转发的 [链接] 纯文本格式
  形如：姓名 日期\\n[链接] 标题\\nhttps://...
  :param text: 原始消息正文
  :return: {"title", "url", "header"} 或 None
  """
  raw = (text or "").strip()
  if not raw or not _LINK_MARKER_RE.search(raw):
    return None
  url_match = _URL_RE.search(raw)
  if not url_match:
    return None
  url = url_match.group(0).rstrip(".,;)")
  title = ""
  header = None
  for line in raw.split("\n"):
    stripped = line.strip()
    if not stripped:
      continue
    if stripped.startswith("http://") or stripped.startswith("https://"):
      continue
    if _LINK_MARKER_RE.search(stripped):
      title = _LINK_MARKER_RE.sub("", stripped).strip()
      continue
    if header is None:
      header = stripped
  if not title:
    title = url
  return {"title": title, "url": url, "header": header}


def format_message_block(body, title=None):
  """
  单条消息块：仅整理正文，不添加额外首行
  :param body: 消息正文
  :param title: 可选标题（链接类消息拼在正文前）
  :return: 格式化文本
  """
  text = normalize_wechat_paste(body)
  if title and title.strip():
    text = f"{title.strip()}\n{text}" if text else title.strip()
  return text


def build_note(msg_type, body, extra_fields=None, title=None, author=None, dt=None):
  """
  组装完整笔记（无 YAML frontmatter，不写入 author/dt 行）
  :param msg_type: 消息类型（保留参数兼容）
  :param body: 正文 Markdown
  :param extra_fields: 兼容旧调用，已忽略
  :param title: 可选标题
  :param author: 兼容旧调用，已忽略
  :param dt: 兼容旧调用，已忽略
  :return: 完整 .md 文本
  """
  return format_message_block(body, title=title)


def format_chat_lines(chat_items):
  """
  将聊天记录列表格式化为 Obsidian 正文
  :param chat_items: [{"sender": "张三", "time": "10:30", "content": "..."}, ...]
  :return: 格式化后的 Markdown 字符串
  """
  lines = []
  for item in chat_items:
    sender = item.get("sender", "未知")
    time_str = item.get("time", "")
    content = item.get("content", "").strip()
    if time_str:
      lines.append(f"{sender}    {time_str}")
    else:
      lines.append(sender)
    lines.append(content)
    lines.append("")
  return "\n".join(lines).strip()


def parse_merged_chat_text(text):
  """
  解析微信合并转发常见的纯文本格式
  支持形如「张三 10:30\\n内容」或「张三：内容」
  :param text: 原始文本
  :return: chat_items 列表，解析失败返回空列表
  """
  blocks = re.split(r"\n\s*\n", text.strip())
  items = []
  header_re = re.compile(
    r"^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$"
  )
  colon_re = re.compile(r"^(.+?)[：:]\s*(.*)$")
  for block in blocks:
    if not block.strip():
      continue
    block_lines = block.strip().split("\n")
    first = block_lines[0].strip()
    m = header_re.match(first)
    if m:
      sender, time_str = m.group(1), m.group(2)
      content = "\n".join(block_lines[1:]).strip() if len(block_lines) > 1 else ""
      items.append({"sender": sender, "time": time_str, "content": content})
      continue
    m2 = colon_re.match(first)
    if m2 and len(block_lines) == 1:
      items.append({
        "sender": m2.group(1).strip(),
        "time": "",
        "content": m2.group(2).strip(),
      })
      continue
    items.append({"sender": "未知", "time": "", "content": block.strip()})
  return items if len(items) >= 2 else []
