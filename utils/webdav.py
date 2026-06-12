# -*- coding: utf-8 -*-
"""WebDAV 上传封装模块"""

import os  # 文件操作
import logging  # 日志
from webdav3.client import Client  # WebDAV 客户端


logger = logging.getLogger(__name__)  # 模块级日志器


class WebDAVUploader:
  """WebDAV 文件上传器，写完即上传、上传后删本地临时文件"""

  def __init__(self, webdav_config, options_config):
    """
    初始化 WebDAV 客户端
    :param webdav_config: webdav 配置节（url / username / password）
    :param options_config: options 配置节（inbox_dir / attachment_dir）
    """
    # 保存远程目录名
    self.inbox_dir = options_config.get("inbox_dir", "Inbox")
    self.attachment_dir = options_config.get("attachment_dir", "Attachments")
    # 规范化 WebDAV 根 URL（去掉末尾斜杠）
    base_url = webdav_config["url"].rstrip("/")
    # 创建 webdavclient3 客户端
    self.client = Client({
      "webdav_hostname": base_url,
      "webdav_login": webdav_config["username"],
      "webdav_password": webdav_config["password"],
    })
    # 确保远程 Inbox 和 Attachments 目录存在
    self._ensure_dirs()

  def _normalize_dir(self, remote_dir):
    """规范化远程目录路径（去掉首尾斜杠）"""
    return (remote_dir or "").strip("/")

  def _ensure_dir(self, remote_dir):
    """确保单个远程目录存在，不存在则递归创建"""
    path = self._normalize_dir(remote_dir)
    if not path:
      return
    try:
      # 已存在则跳过
      if self.client.check(path):
        return
    except Exception:
      # check 失败时继续尝试创建
      pass
    try:
      # 递归创建父级目录
      self.client.mkdir(path, create_parents=True)
      logger.info("已创建远程目录: %s", path)
    except Exception as exc:
      logger.warning("创建远程目录 %s 失败: %s", path, exc)

  def _ensure_dirs(self):
    """确保远程 Inbox 与 Attachments 目录存在"""
    for remote_dir in (self.inbox_dir, self.attachment_dir):
      self._ensure_dir(remote_dir)

  def upload_note(self, local_path, remote_filename):
    """
    上传 Markdown 笔记到 Inbox，成功后删除本地临时文件
    :param local_path: 本地临时 .md 路径
    :param remote_filename: 远程文件名（不含目录）
    :return: 远程完整路径
    """
    # 上传前再次确保目录存在（避免初始化时创建失败）
    self._ensure_dir(self.inbox_dir)
    # 拼接远程路径
    remote_path = f"{self._normalize_dir(self.inbox_dir)}/{remote_filename}"
    # 执行同步上传
    self.client.upload_sync(remote_path=remote_path, local_path=local_path)
    # 上传成功后删除本地临时文件
    self._remove_local(local_path)
    logger.info("笔记已上传: %s", remote_path)
    # 返回远程路径供调用方记录
    return remote_path

  def upload_attachment(self, local_path, remote_filename):
    """
    上传附件到 Attachments，成功后删除本地临时文件
    :param local_path: 本地临时文件路径
    :param remote_filename: 远程文件名
    :return: 远程完整路径
    """
    # 上传前确保附件目录存在
    self._ensure_dir(self.attachment_dir)
    # 拼接远程附件路径
    remote_path = f"{self._normalize_dir(self.attachment_dir)}/{remote_filename}"
    # 同步上传附件
    self.client.upload_sync(remote_path=remote_path, local_path=local_path)
    # 删除本地临时文件
    self._remove_local(local_path)
    logger.info("附件已上传: %s", remote_path)
    # 返回远程路径
    return remote_path

  def _remove_local(self, local_path):
    """安全删除本地临时文件"""
    try:
      # 仅当文件仍存在时删除
      if os.path.isfile(local_path):
        os.remove(local_path)
    except OSError as exc:
      # 删除失败记日志
      logger.warning("删除临时文件失败 %s: %s", local_path, exc)
