# -*- coding: utf-8 -*-
"""微信公众号图片页与 CDN 图片保存"""

import logging  # 日志
from datetime import datetime  # 文件名时间戳
from handlers.base import BaseHandler  # 基类
from utils.temp import write_temp_bytes  # 临时文件
from utils.weixin_article import (  # 图片下载
  download_image_bytes,
  image_ext_from_url,
  is_direct_image_url,
  resolve_weixin_url,
)


logger = logging.getLogger(__name__)  # 模块日志
# 单条消息最多保存的图片张数
_MAX_IMAGES = 20


class WeixinMediaHandler(BaseHandler):
  """下载微信图片并写入 Obsidian 笔记"""

  def handle_image_urls(
    self,
    image_urls,
    openid=None,
    header=None,
    source_url=None,
    title=None,
    from_image_marker=False,
  ):
    """将图片 URL 列表下载到 Attachments 并生成笔记（失败时用远程链接）"""
    if not image_urls:
      logger.warning("图片 URL 列表为空: %s", source_url)
      return False
    attachment_dir = self.options.get("attachment_dir", "Attachments")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    body_parts = []
    if header:
      body_parts.append(header)
      body_parts.append("")
    label = title or "图片"
    body_parts.append(f"[图片] {label}")
    if source_url:
      body_parts.append(source_url)
    wiki_lines = []
    saved_local = 0
    for idx, img_url in enumerate(image_urls[:_MAX_IMAGES]):
      line = f"![]({img_url})"
      try:
        data = download_image_bytes(img_url)
        if data:
          ext = image_ext_from_url(img_url)
          filename = f"weixin_{ts}_{idx + 1}{ext}"
          local_path = write_temp_bytes(data, filename)
          self.uploader.upload_attachment(local_path, filename)
          line = f"![[{attachment_dir}/{filename}]]"
          saved_local += 1
      except Exception as exc:
        logger.warning("图片保存失败，改用远程链接 %s: %s", img_url[:60], exc)
      wiki_lines.append(line)
    body_parts.append("")
    body_parts.extend(wiki_lines)
    body = "\n".join(body_parts)
    self.save_note("image", body, openid=openid)
    logger.info("已保存微信图片 本地 %d 张 / 共 %d 张", saved_local, len(wiki_lines))
    return True

  def handle_weixin_url(
    self,
    url,
    openid=None,
    header=None,
    title=None,
    from_image_marker=False,
    resolved=None,
  ):
    """解析公众号链接，若为图片页则下载保存"""
    if resolved is None:
      timeout = self.options.get("jina_timeout", 30)
      resolved = resolve_weixin_url(url, timeout=timeout)
    if not resolved:
      logger.warning("公众号页面解析失败: %s", url)
      return False
    if resolved.get("kind") != "images":
      return False
    page_title = title or resolved.get("title") or "图片"
    return self.handle_image_urls(
      resolved["urls"],
      openid=openid,
      header=header,
      source_url=url,
      title=page_title,
      from_image_marker=from_image_marker,
    )

  def handle_direct_image_url(self, url, openid=None, header=None):
    """处理 mmbiz.qpic.cn 等直链图片"""
    if not is_direct_image_url(url):
      return False
    return self.handle_image_urls(
      [url],
      openid=openid,
      header=header,
      source_url=url,
      title="图片",
      from_image_marker=True,
    )
