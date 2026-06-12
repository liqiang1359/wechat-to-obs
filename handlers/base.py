# -*- coding: utf-8 -*-
"""处理器公共基类与工具"""

import logging  # 日志
from utils.batch import get_note_batcher  # 全局消息合并器


logger = logging.getLogger(__name__)  # 模块日志


class BaseHandler:
  """消息处理器基类，封装笔记写入与 WebDAV 上传"""

  def __init__(self, uploader, options):
    """
    :param uploader: WebDAVUploader 实例
    :param options: options 配置节
    """
    self.uploader = uploader  # WebDAV 上传器
    self.options = options  # 业务选项
    # 全局单例批处理器（同一用户窗口内合并到同一文件）
    self.batcher = get_note_batcher(options)

  def save_note(self, msg_type, body, extra_fields=None, title=None, openid=None):
    """
    生成 .md 并上传到 Inbox（支持短时间窗口内合并）
    :param openid: 微信用户 OpenID，用于合并判断
    :return: 远程路径
    """
    remote_path = self.batcher.save_note(
      self.uploader,
      openid,
      msg_type,
      body,
      extra_fields=extra_fields,
      title=title,
    )
    logger.info("已保存 %s 类型笔记: %s", msg_type, remote_path)
    return remote_path
