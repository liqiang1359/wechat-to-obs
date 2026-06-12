# -*- coding: utf-8 -*-
"""纯文字消息处理器"""

import logging  # 日志
from handlers.base import BaseHandler  # 基类
from handlers.chat import ChatHandler  # 合并聊天记录检测
from utils.markdown import parse_merged_chat_text  # 聊天记录解析


logger = logging.getLogger(__name__)  # 模块日志


class TextHandler(BaseHandler):
  """处理微信 text 类型消息"""

  def handle(self, message):
    """
    处理文字消息，自动识别是否为合并转发聊天记录
    :param message: wechatpy TextMessage
    """
    # 获取消息正文
    content = (message.content or "").strip()
    # 空消息直接忽略
    if not content:
      logger.warning("收到空文字消息，已忽略")
      return
    # 尝试解析为合并聊天记录
    chat_items = parse_merged_chat_text(content)
    if len(chat_items) >= 2:
      # 委托聊天记录处理器
      logger.info("文字消息识别为合并聊天记录，共 %d 条", len(chat_items))
      ChatHandler(self.uploader, self.options).handle_items(chat_items)
      return
    # 普通文字笔记（同一用户 3 分钟内连续发送会合并到同一文件）
    openid = getattr(message, "source", None)
    self.save_note("text", content, openid=openid)
    logger.info("已处理纯文字消息")
