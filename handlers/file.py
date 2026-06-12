# -*- coding: utf-8 -*-
"""图片与媒体文件处理器"""

import logging  # 日志
import os  # 扩展名
from datetime import datetime  # 文件名时间戳
from handlers.base import BaseHandler  # 基类
from utils.temp import write_temp_bytes  # 临时二进制文件


logger = logging.getLogger(__name__)  # 模块日志

# 微信媒体类型到文件扩展名映射
MEDIA_EXT_MAP = {
  "image": ".jpg",
  "voice": ".amr",
  "video": ".mp4",
  "shortvideo": ".mp4",
}


class FileHandler(BaseHandler):
  """下载微信媒体并上传 WebDAV Attachments"""

  def __init__(self, uploader, options, wechat_client):
    """
    :param wechat_client: wechatpy WeChatClient，用于下载 media_id
    """
    super().__init__(uploader, options)
    self.wechat_client = wechat_client  # 微信 API 客户端

  def handle_image(self, message):
    """
    处理图片消息
    :param message: wechatpy ImageMessage
    """
    self._handle_media(
      media_id=message.media_id,
      media_type="image",
      extra_fields={"media_id": message.media_id},
      pic_url=getattr(message, "image", None) or getattr(message, "pic_url", None),
    )

  def handle_voice(self, message):
    """处理语音消息"""
    self._handle_media(
      media_id=message.media_id,
      media_type="voice",
      extra_fields={"media_id": message.media_id},
    )

  def handle_video(self, message, short=False):
    """处理视频或短视频消息"""
    media_type = "shortvideo" if short else "video"
    self._handle_media(
      media_id=message.media_id,
      media_type=media_type,
      extra_fields={"media_id": message.media_id},
    )

  def _handle_media(self, media_id, media_type, extra_fields=None, pic_url=None):
    """
    通用媒体下载、上传与笔记生成
    :param media_id: 微信媒体 ID
    :param media_type: image/voice/video 等
    :param extra_fields: frontmatter 扩展字段
    :param pic_url: 图片直链（备用）
    """
    # 无 media_id 无法下载
    if not media_id:
      logger.warning("媒体消息缺少 media_id，已忽略")
      return
    # 默认扩展名
    ext = MEDIA_EXT_MAP.get(media_type, ".bin")
    # 带时间戳的附件文件名
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    attach_name = f"{media_type}_{ts}{ext}"
    local_path = None
    try:
      # 通过微信 API 下载媒体二进制
      res = self.wechat_client.media.download(media_id)
      # 写入临时文件
      local_path = write_temp_bytes(res.content, attach_name)
      # 上传到 WebDAV Attachments
      remote_path = self.uploader.upload_attachment(local_path, attach_name)
      # Obsidian wiki 链接引用附件
      attachment_dir = self.options.get("attachment_dir", "Attachments")
      wiki_ref = f"![[{attachment_dir}/{attach_name}]]"
      # 笔记正文
      body_lines = [wiki_ref]
      if pic_url:
        body_lines.append("")
        body_lines.append(f"原始图片链接: {pic_url}")
      body = "\n".join(body_lines)
      # frontmatter
      fields = {"media_type": media_type}
      if extra_fields:
        fields.update(extra_fields)
      if pic_url:
        fields["pic_url"] = pic_url
      # 保存引用笔记到 Inbox
      note_type = "image" if media_type == "image" else "file"
      self.save_note(note_type, body, extra_fields=fields, title=attach_name)
      logger.info("已处理媒体 %s -> %s", media_type, remote_path)
    except Exception as exc:
      # 下载或上传失败
      logger.error("处理媒体失败 media_id=%s: %s", media_id, exc)
      # 清理未上传成功的临时文件
      if local_path and os.path.isfile(local_path):
        try:
          os.remove(local_path)
        except OSError:
          pass
