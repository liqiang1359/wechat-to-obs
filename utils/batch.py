# -*- coding: utf-8 -*-
"""短时间窗口内合并多条消息为同一笔记文件"""

import logging  # 日志
import threading  # 并发锁
from datetime import datetime  # 时间窗口判断

from utils.markdown import build_note, make_filename  # 笔记生成
from utils.temp import write_temp_file  # 临时文件


logger = logging.getLogger(__name__)  # 模块日志


class NoteBatcher:
  """按用户 OpenID + 时间窗口合并连续消息"""

  def __init__(self, options):
    """
    :param options: 配置中的 options 节
    """
    # 是否启用合并
    self.enabled = bool(options.get("merge_enabled", True))
    # 合并时间窗口（秒），默认 3 分钟
    self.window_sec = int(options.get("merge_window_seconds", 180))
    # 用户会话：openid -> 会话信息
    self._sessions = {}
    # 保护会话字典的锁
    self._lock = threading.Lock()

  def save_note(self, uploader, openid, msg_type, body, extra_fields=None, title=None):
    """
    保存或追加笔记（窗口内合并到同一文件）
  :return: 远程路径
    """
    # 未启用或无 openid 时按单条保存
    if not self.enabled or not openid:
      return self._save_single(
        uploader, msg_type, body, extra_fields=extra_fields, title=title
      )

    now = datetime.now()
    with self._lock:
      session = self._sessions.get(openid)
      # 窗口内则追加到已有文件
      if session and self._in_window(session["last_at"], now):
        return self._append_to_session(uploader, session, now, body, title)
      # 超时则开启新会话
      return self._start_session(
        uploader, openid, now, msg_type, body,
        extra_fields=extra_fields, title=title,
      )

  def _in_window(self, last_at, now):
    """判断两次消息是否在合并窗口内"""
    return (now - last_at).total_seconds() <= self.window_sec

  def _start_session(self, uploader, openid, now, msg_type, body,
                     extra_fields=None, title=None):
    """创建新笔记文件并记录会话"""
    # 合并模式统一用 note 作为文件名类型
    filename = make_filename("note", now)
    # 生成首条完整笔记
    content = build_note(msg_type, body, extra_fields, title)
    remote_path = self._upload_content(uploader, content, filename)
    # 记录会话状态
    self._sessions[openid] = {
      "filename": filename,
      "started_at": now,
      "last_at": now,
      "content": content,
    }
    logger.info("新建合并笔记: %s (窗口 %ds)", remote_path, self.window_sec)
    return remote_path

  def _append_to_session(self, uploader, session, now, body, title=None):
    """向当前会话文件追加一条消息"""
    # 追加块：时间分隔线 + 可选小标题 + 正文
    block_lines = [
      "",
      "---",
      "",
      f"**{now.strftime('%H:%M:%S')}**",
      "",
    ]
    if title:
      block_lines.append(f"### {title}")
      block_lines.append("")
    block_lines.append(body.strip())
    append_text = "\n".join(block_lines)
    # 合并到会话全文
    session["content"] = session["content"] + append_text
    session["last_at"] = now
    # 覆盖上传同一远程文件
    remote_path = self._upload_content(
      uploader, session["content"], session["filename"]
    )
    logger.info("已追加到合并笔记: %s", remote_path)
    return remote_path

  def _save_single(self, uploader, msg_type, body, extra_fields=None, title=None):
    """不合并，每条消息单独一个文件（旧行为）"""
    content = build_note(msg_type, body, extra_fields, title)
    filename = make_filename(msg_type)
    remote_path = self._upload_content(uploader, content, filename)
    logger.info("已保存单条笔记: %s", remote_path)
    return remote_path

  def _upload_content(self, uploader, content, filename):
    """将 Markdown 文本写入临时文件并上传 WebDAV"""
    local_path = write_temp_file(content, filename)
    return uploader.upload_note(local_path, filename)
