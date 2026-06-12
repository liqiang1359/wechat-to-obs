# -*- coding: utf-8 -*-
"""合并转发聊天记录处理器"""

import logging  # 日志
import xml.etree.ElementTree as ET  # 解析嵌套 XML
from handlers.base import BaseHandler  # 基类
from utils.markdown import format_chat_lines, parse_merged_chat_text  # 格式化


logger = logging.getLogger(__name__)  # 模块日志


class ChatHandler(BaseHandler):
  """解析并保存微信合并转发的聊天记录"""

  def handle_items(self, chat_items):
    """
    将已解析的聊天条目写入 Obsidian
    :param chat_items: [{"sender","time","content"}, ...]
    """
    # 格式化为 Markdown 正文
    body = format_chat_lines(chat_items)
    # 保存 chat 类型笔记
    self.save_note("chat", body)
    logger.info("已保存聊天记录，共 %d 条", len(chat_items))

  def handle_raw_xml(self, raw_xml):
    """
    尝试从原始 XML 中解析合并转发记录（部分客户端格式）
    :param raw_xml: 微信 POST 原始 XML 字符串
    """
    try:
      # 解析 XML 根节点
      root = ET.fromstring(raw_xml)
      items = []
      # 查找 RecordInfo 或嵌套 msg 节点（合并转发常见结构）
      for record in root.iter("recorditem"):
        # 嵌套 recorditem 内可能还有 XML
        inner = record.text or ""
        if inner.strip().startswith("<"):
          try:
            inner_root = ET.fromstring(inner)
            for msg in inner_root.iter("msg"):
              sender = self._xml_text(msg, "sourcename") or self._xml_text(msg, "fromnickname")
              time_str = self._xml_text(msg, "sourcetime") or self._xml_text(msg, "createtime")
              content = self._xml_text(msg, "datadesc") or self._xml_text(msg, "content")
              if content:
                items.append({
                  "sender": sender or "未知",
                  "time": self._normalize_time(time_str),
                  "content": content,
                })
          except ET.ParseError:
            pass
      # XML 解析成功
      if len(items) >= 2:
        self.handle_items(items)
        return True
    except ET.ParseError as exc:
      logger.debug("聊天记录 XML 解析失败: %s", exc)
    return False

  def handle_text_fallback(self, text):
    """
    从纯文本降级解析合并聊天记录
    :param text: 消息正文
    """
    items = parse_merged_chat_text(text)
    if len(items) >= 2:
      self.handle_items(items)
      return True
    return False

  @staticmethod
  def _xml_text(node, tag):
    """安全获取子节点文本"""
    child = node.find(tag)
    return child.text.strip() if child is not None and child.text else ""

  @staticmethod
  def _normalize_time(time_str):
    """将微信时间戳或时间字符串简化为 HH:MM"""
    if not time_str:
      return ""
    # 纯数字视为 Unix 时间戳
    if time_str.isdigit() and len(time_str) >= 10:
      from datetime import datetime
      try:
        ts = int(time_str[:10])
        return datetime.fromtimestamp(ts).strftime("%H:%M")
      except (ValueError, OSError):
        return time_str
    return time_str
