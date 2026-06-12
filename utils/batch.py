# -*- coding: utf-8 -*-
"""短时间窗口内合并多条消息为同一笔记文件"""

import logging  # 日志
import threading  # 并发锁
from datetime import datetime  # 时间窗口判断

from utils.markdown import make_filename, format_message_block  # 笔记生成
from utils.temp import write_temp_file  # 临时文件


logger = logging.getLogger(__name__)  # 模块日志

# 全局单例批处理器（所有 Handler 共享同一会话状态）
_global_batcher = None
_global_batcher_lock = threading.Lock()


def get_note_batcher(options):
  """获取全局 NoteBatcher 单例，避免每条消息新建导致无法合并"""
  global _global_batcher
  with _global_batcher_lock:
    if _global_batcher is None:
      _global_batcher = NoteBatcher(options)
    return _global_batcher


class NoteBatcher:
  """按用户 OpenID + 时间窗口合并连续消息"""

  def __init__(self, options):
    """
    :param options: 配置中的 options 节
    """
    self.enabled = bool(options.get("merge_enabled", True))
    self.window_sec = int(options.get("merge_window_seconds", 300))
    self._sessions = {}
    self._lock = threading.Lock()

  def save_note(self, uploader, openid, msg_type, body, extra_fields=None, title=None):
    """
    保存或追加笔记（窗口内合并到同一文件）
    :return: 远程路径
    """
    if not self.enabled or not openid:
      return self._save_single(
        uploader, msg_type, body, extra_fields=extra_fields, title=title
      )

    now = datetime.now()
    with self._lock:
      session = self._sessions.get(openid)
      if session and self._in_window(session["last_at"], now):
        return self._append_to_session(uploader, session, now, body)
      return self._start_session(
        uploader, openid, now, msg_type, body, title=title
      )

  def _in_window(self, last_at, now):
    """判断两次消息是否在合并窗口内"""
    return (now - last_at).total_seconds() <= self.window_sec

  def _start_session(self, uploader, openid, now, msg_type, body, title=None):
    """创建新笔记文件并记录会话"""
    filename = make_filename("note", now)
    content = format_message_block(body)
    self._sessions[openid] = {
      "filename": filename,
      "started_at": now,
      "last_at": now,
      "content": content,
    }
    remote_path = self._upload_content(uploader, content, filename)
    logger.info("新建合并笔记: %s (窗口 %ds)", remote_path, self.window_sec)
    return remote_path

  def _append_to_session(self, uploader, session, now, body):
    """向当前会话文件追加一条消息"""
    append_text = "\n\n" + format_message_block(body)
    session["content"] = session["content"] + append_text
    session["last_at"] = now
    remote_path = self._upload_content(
      uploader, session["content"], session["filename"]
    )
    logger.info("已追加到合并笔记: %s", remote_path)
    return remote_path

  def _save_single(self, uploader, msg_type, body, extra_fields=None, title=None):
    """不合并，每条消息单独一个文件"""
    now = datetime.now()
    content = format_message_block(body, title=title)
    filename = make_filename(msg_type, now)
    remote_path = self._upload_content(uploader, content, filename)
    logger.info("已保存单条笔记: %s", remote_path)
    return remote_path

  def _upload_content(self, uploader, content, filename):
    """将 Markdown 文本写入临时文件并上传 WebDAV"""
    local_path = write_temp_file(content, filename)
    return uploader.upload_note(local_path, filename)
