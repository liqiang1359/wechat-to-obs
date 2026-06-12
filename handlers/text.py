# -*- coding: utf-8 -*-
"""纯文字消息处理器"""

import logging  # 日志
from handlers.base import BaseHandler  # 基类
from handlers.chat import ChatHandler  # 合并聊天记录检测
from handlers.link import LinkHandler  # 链接抓取
from handlers.weixin_media import WeixinMediaHandler  # 图片页
from utils.markdown import (  # 解析
  parse_merged_chat_text,
  parse_wechat_shared_link,
  parse_wechat_shared_image,
)

logger = logging.getLogger(__name__)  # 模块日志


class TextHandler(BaseHandler):
  """处理微信 text 类型消息"""

  def handle(self, message):
    """
    处理文字消息，自动识别聊天记录、[图片]、[链接]、普通文字
    :param message: wechatpy TextMessage
    """
    content = (message.content or "").strip()
    if not content:
      logger.warning("收到空文字消息，已忽略")
      return
    openid = getattr(message, "source", None)
    chat_items = parse_merged_chat_text(content)
    if len(chat_items) >= 2:
      logger.info("文字消息识别为合并聊天记录，共 %d 条", len(chat_items))
      ChatHandler(self.uploader, self.options).handle_items(chat_items)
      return
    image_info = parse_wechat_shared_image(content)
    if image_info:
      logger.info("文字消息识别为 [图片] 转发: %s", image_info["url"][:60])
      media = WeixinMediaHandler(self.uploader, self.options)
      if media.handle_weixin_url(
        image_info["url"],
        openid=openid,
        header=image_info.get("header"),
        title=image_info["title"],
        from_image_marker=True,
      ):
        return
      media.handle_direct_image_url(
        image_info["url"],
        openid=openid,
        header=image_info.get("header"),
      )
      return
    link_info = parse_wechat_shared_link(content)
    if link_info:
      logger.info("文字消息识别为 [链接] 转发: %s", link_info["url"][:60])
      LinkHandler(self.uploader, self.options).handle(
        title=link_info["title"],
        url=link_info["url"],
        header=link_info.get("header"),
        from_link_marker=True,
        openid=openid,
      )
      return
    if LinkHandler(self.uploader, self.options).handle_from_text(content, openid=openid):
      logger.info("文字消息识别为含 URL 的链接或图片")
      return
    self.save_note("text", content, openid=openid)
    logger.info("已处理纯文字消息")
