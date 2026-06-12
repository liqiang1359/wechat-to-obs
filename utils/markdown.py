# -*- coding: utf-8 -*-
"""Markdown 笔记生成模块"""

import re  # 正则解析聊天记录
from datetime import datetime  # 时间戳与文件名


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


def format_message_block(author, body, dt=None, title=None):
  """
  单条消息块：第一行「姓名 + 日期」，第二行起为正文
  :param author: 显示在首行的姓名
  :param body: 消息正文（纯文字仅一行）
  :param dt: 消息时间
  :param title: 可选标题（仅链接类消息使用，拼在正文前）
  :return: 格式化文本
  """
  when = dt or datetime.now()
  date_str = when.strftime("%Y-%m-%d %H:%M:%S")
  header = f"{author}    {date_str}"
  text = (body or "").strip()
  if title and title.strip():
    text = f"{title.strip()}\n{text}" if text else title.strip()
  return f"{header}\n{text}"


def build_note(msg_type, body, extra_fields=None, title=None, author="微信用户", dt=None):
  """
  组装完整笔记（无 YAML frontmatter）
  :param msg_type: 消息类型（保留参数兼容，不再写入 frontmatter）
  :param body: 正文 Markdown
  :param extra_fields: 兼容旧调用，已忽略
  :param title: 可选标题
  :param author: 首行显示的姓名
  :param dt: 消息时间
  :return: 完整 .md 文本
  """
  return format_message_block(author, body, dt=dt, title=title)


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
