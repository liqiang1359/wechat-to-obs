# -*- coding: utf-8 -*-
"""处理器公共基类与工具"""

import logging  # 日志
from utils.markdown import build_note, make_filename  # Markdown 生成
from utils.temp import write_temp_file  # 临时文件


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

  def save_note(self, msg_type, body, extra_fields=None, title=None):
    """
    生成 .md 并上传到 Inbox
    :return: 远程路径
    """
    # 组装完整笔记内容
    note_content = build_note(msg_type, body, extra_fields, title)
    # 生成文件名
    filename = make_filename(msg_type)
    # 写入本地临时文件
    local_path = write_temp_file(note_content, filename)
    # 上传到 WebDAV Inbox
    remote_path = self.uploader.upload_note(local_path, filename)
    logger.info("已保存 %s 类型笔记: %s", msg_type, remote_path)
    return remote_path
