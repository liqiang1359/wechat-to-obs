# -*- coding: utf-8 -*-
"""Markdown 笔记生成模块"""

import re  # 正则解析聊天记录
from datetime import datetime  # 时间戳与文件名


def make_filename(msg_type, dt=None):
  """
  生成 Obsidian 笔记文件名：YYYYMMDD-HHMMSS-类型.md
  :param msg_type: 消息类型 text/link/image/file/chat
  :param dt: 可选 datetime，默认当前时间
  :return: 文件名字符串
  """
  # 默认使用当前时间
  when = dt or datetime.now()
  # 格式化时间前缀
  time_part = when.strftime("%Y%m%d-%H%M%S")
  # 拼接类型后缀
  return f"{time_part}-{msg_type}.md"


def build_frontmatter(fields):
  """
  构建 YAML frontmatter 块
  :param fields: 键值对字典
  :return: frontmatter 字符串（含首尾 ---）
  """
  # frontmatter 行列表
  lines = ["---"]
  # 逐字段写入
  for key, value in fields.items():
    # 跳过空值字段
    if value is None:
      continue
    # 字符串中含冒号时加引号
    if isinstance(value, str) and (":" in value or "\n" in value):
      lines.append(f'{key}: "{value}"')
    else:
      lines.append(f"{key}: {value}")
  # 闭合 frontmatter
  lines.append("---")
  # 换行拼接
  return "\n".join(lines)


def build_note(msg_type, body, extra_fields=None, title=None):
  """
  组装完整 Markdown 笔记（frontmatter + 正文）
  :param msg_type: 消息类型
  :param body: 正文 Markdown
  :param extra_fields: 额外 frontmatter 字段
  :param title: 可选一级标题
  :return: 完整 .md 文本
  """
  # 基础 frontmatter 字段
  fields = {
    "source": "wechat",
    "type": msg_type,
    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  }
  # 合并调用方传入的额外字段
  if extra_fields:
    fields.update(extra_fields)
  # 生成 frontmatter
  fm = build_frontmatter(fields)
  # 正文部分列表
  parts = [fm, ""]
  # 有标题时添加一级标题
  if title:
    parts.append(f"# {title}")
    parts.append("")
  # 追加正文
  parts.append(body.strip())
  # 合并为完整笔记
  return "\n".join(parts)


def format_chat_lines(chat_items):
  """
  将聊天记录列表格式化为 Obsidian 正文
  :param chat_items: [{"sender": "张三", "time": "10:30", "content": "..."}, ...]
  :return: 格式化后的 Markdown 字符串
  """
  # 输出行列表
  lines = []
  # 遍历每条聊天
  for item in chat_items:
    sender = item.get("sender", "未知")
    time_str = item.get("time", "")
    content = item.get("content", "").strip()
    # 发送者与时间行
    if time_str:
      lines.append(f"**{sender}** {time_str}")
    else:
      lines.append(f"**{sender}**")
    # 消息内容
    lines.append(content)
    # 条目间空行
    lines.append("")
  # 去掉末尾多余空行
  return "\n".join(lines).strip()


def parse_merged_chat_text(text):
  """
  解析微信合并转发常见的纯文本格式
  支持形如「张三 10:30\\n内容」或「张三：内容」
  :param text: 原始文本
  :return: chat_items 列表，解析失败返回空列表
  """
  # 按空行分段
  blocks = re.split(r"\n\s*\n", text.strip())
  items = []
  # 匹配「姓名 时:分」或「姓名：」
  header_re = re.compile(
    r"^(.+?)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$"
  )
  colon_re = re.compile(r"^(.+?)[：:]\s*(.*)$")
  # 逐段解析
  for block in blocks:
  # 跳过空段
    if not block.strip():
      continue
    block_lines = block.strip().split("\n")
    first = block_lines[0].strip()
    # 尝试「姓名 时间」格式
    m = header_re.match(first)
    if m:
      sender, time_str = m.group(1), m.group(2)
      content = "\n".join(block_lines[1:]).strip() if len(block_lines) > 1 else ""
      items.append({"sender": sender, "time": time_str, "content": content})
      continue
    # 尝试「姓名：内容」单行格式
    m2 = colon_re.match(first)
    if m2 and len(block_lines) == 1:
      items.append({
        "sender": m2.group(1).strip(),
        "time": "",
        "content": m2.group(2).strip(),
      })
      continue
    # 无法识别则作为匿名消息
    items.append({"sender": "未知", "time": "", "content": block.strip()})
  # 至少两条才认为是合并聊天记录
  return items if len(items) >= 2 else []
