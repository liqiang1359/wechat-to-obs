# -*- coding: utf-8 -*-
"""WebDAV 上传封装模块"""

import os  # 文件操作
import logging  # 日志
from urllib.parse import quote, urljoin  # URL 编码与拼接
import requests  # 直接 PUT 上传回退
from requests.auth import HTTPBasicAuth  # 基础认证
from webdav3.client import Client  # WebDAV 客户端


logger = logging.getLogger(__name__)  # 模块级日志器


def _encode_base_url(url):
  """对 WebDAV 根 URL 中的中文路径进行编码"""
  if "://" not in url:
    return url.rstrip("/")
  scheme, rest = url.split("://", 1)
  if "/" not in rest:
    return url.rstrip("/")
  host, path = rest.split("/", 1)
  # 逐段编码路径，保留斜杠
  encoded_path = "/".join(quote(part, safe="") for part in path.split("/") if part)
  return f"{scheme}://{host}/{encoded_path}".rstrip("/")


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
    # 保存认证信息供直接 PUT 使用
    self.base_url = _encode_base_url(webdav_config["url"])
    self.username = webdav_config["username"]
    self.password = webdav_config["password"]
    # 创建 webdavclient3 客户端（跳过 PROPFIND，部分服务器对 check 返回 403）
    self.client = Client({
      "webdav_hostname": self.base_url,
      "webdav_login": self.username,
      "webdav_password": self.password,
      "webdav_disable_check": True,
    })
    # 目录是否已检查过
    self._dirs_ready = False
    # 尝试确保远程目录存在
    self._ensure_dirs()
    self._dirs_ready = True

  def _normalize_dir(self, remote_dir):
    """规范化远程目录路径（去掉首尾斜杠）"""
    return (remote_dir or "").strip("/")

  def _remote_file_url(self, remote_path):
    """拼接远程文件的完整 URL"""
    clean = remote_path.lstrip("/")
    return urljoin(self.base_url + "/", quote(clean, safe="/"))

  def _put_file_direct(self, remote_path, local_path):
    """使用 HTTP PUT 直接上传（绕过 webdav3 的 check）"""
    target_url = self._remote_file_url(remote_path)
    with open(local_path, "rb") as fp:
      response = requests.put(
        target_url,
        data=fp,
        auth=HTTPBasicAuth(self.username, self.password),
        timeout=60,
      )
    if response.status_code not in (200, 201, 204):
      raise RuntimeError(
        f"PUT 上传失败 {response.status_code}: {target_url} -> {response.text[:200]}"
      )
    logger.info("PUT 上传成功: %s", remote_path)

  def _upload_file(self, remote_path, local_path):
    """优先 webdav3 上传，失败时回退到直接 PUT"""
    try:
      self.client.upload_file(
        remote_path=remote_path,
        local_path=local_path,
        force=True,
      )
    except Exception as exc:
      logger.warning("webdav3 上传失败，尝试 PUT: %s", exc)
      self._put_file_direct(remote_path, local_path)

  def _ensure_dir(self, remote_dir):
    """确保单个远程目录存在，不存在则尝试创建"""
    path = self._normalize_dir(remote_dir)
    if not path:
      return
    try:
      self.client.mkdir(path, recursive=True)
      logger.info("已创建远程目录: %s", path)
    except Exception as exc:
      # 目录可能已存在，或 WebDAV 禁止 MKCOL，忽略继续尝试上传
      logger.warning("创建远程目录 %s 跳过: %s", path, exc)

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
    if not self._dirs_ready:
      self._ensure_dir(self.inbox_dir)
    remote_path = f"{self._normalize_dir(self.inbox_dir)}/{remote_filename}"
    self._upload_file(remote_path, local_path)
    self._remove_local(local_path)
    logger.info("笔记已上传: %s", remote_path)
    return remote_path

  def upload_attachment(self, local_path, remote_filename):
    """
    上传附件到 Attachments，成功后删除本地临时文件
    :param local_path: 本地临时文件路径
    :param remote_filename: 远程文件名
    :return: 远程完整路径
    """
    self._ensure_dir(self.attachment_dir)
    remote_path = f"{self._normalize_dir(self.attachment_dir)}/{remote_filename}"
    self._upload_file(remote_path, local_path)
    self._remove_local(local_path)
    logger.info("附件已上传: %s", remote_path)
    return remote_path

  def _remove_local(self, local_path):
    """安全删除本地临时文件"""
    try:
      if os.path.isfile(local_path):
        os.remove(local_path)
    except OSError as exc:
      logger.warning("删除临时文件失败 %s: %s", local_path, exc)
