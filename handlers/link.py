# -*- coding: utf-8 -*-
"""链接消息处理器（含 Jina Reader 全文抓取）"""

import logging  # 日志
import re  # URL 提取
import requests  # HTTP 请求 Jina
from handlers.base import BaseHandler  # 基类
from handlers.weixin_media import WeixinMediaHandler  # 公众号图片
from utils.weixin_article import (  # 公众号专用抓取
  is_weixin_article_url,
  is_direct_image_url,
  is_blocked_content,
  resolve_weixin_url,
)


logger = logging.getLogger(__name__)  # 模块日志
# Jina Reader API 前缀
JINA_READER_BASE = "https://r.jina.ai/"
# 从纯文本提取 URL
_URL_RE = re.compile(r"https?://[^\s\]\)】]+")
# 公众号短链（常见于图片分享）
_WEIXIN_SHORT_RE = re.compile(r"https?://mp\.weixin\.qq\.com/s/[\w\-]+")
# 页面打不开时的提示
_WEIXIN_FALLBACK_HINT = (
  "> 公众号页面无法在服务器端打开（微信反爬限制），"
  "请直接点击上方链接在微信中查看。"
)


class LinkHandler(BaseHandler):
  """处理 link 类型及图文消息中的链接"""

  def handle(
    self,
    title,
    url,
    description=None,
    openid=None,
    header=None,
    from_link_marker=False,
  ):
    """处理链接卡片或微信 [链接] 转发"""
    url = (url or "").strip()
    title = (title or "链接").strip()
    if title == url or title.startswith("http"):
      title = "链接"
    if self._try_weixin_media(url, openid=openid, header=header, title=title):
      return
    if _WEIXIN_SHORT_RE.match(url):
      self._save_weixin_short_fallback(url, openid=openid, header=header, title=title)
      return
    body_parts = []
    if header:
      body_parts.append(header)
      body_parts.append("")
    if from_link_marker:
      body_parts.append(f"[链接] {title}")
    else:
      body_parts.append(title)
    body_parts.append(url)
    fetch_failed = False
    if self.options.get("fetch_full_article", True) and url:
      article_md = self._fetch_full_article(url)
      if article_md:
        body_parts.append("")
        body_parts.append(article_md)
      else:
        fetch_failed = True
        if is_weixin_article_url(url):
          body_parts.append("")
          body_parts.append(_WEIXIN_FALLBACK_HINT)
        logger.warning("文章抓取失败，已降级为标题+URL: %s", url)
    body = "\n".join(body_parts)
    self.save_note("link", body, openid=openid)
    status = "降级" if fetch_failed else "全文"
    logger.info("已处理链接(%s): %s", status, url)

  def handle_from_text(self, text, openid=None):
    """从纯文本中提取 [链接]、[图片] 或 URL 并处理"""
    from utils.markdown import parse_wechat_shared_link, parse_wechat_shared_image

    image_info = parse_wechat_shared_image(text)
    if image_info:
      if self._try_weixin_media(
        image_info["url"],
        openid=openid,
        header=image_info.get("header"),
        title=image_info["title"],
        from_image_marker=True,
      ):
        return True
    link_info = parse_wechat_shared_link(text)
    if link_info:
      self.handle(
        title=link_info["title"],
        url=link_info["url"],
        header=link_info.get("header"),
        from_link_marker=True,
        openid=openid,
      )
      return True
    url_match = _URL_RE.search(text or "")
    if not url_match:
      return False
    url = url_match.group(0).rstrip(".,;)")
    if self._try_weixin_media(url, openid=openid, from_image_marker=True):
      return True
    if _WEIXIN_SHORT_RE.match(url):
      self._save_weixin_short_fallback(url, openid=openid)
      return True
    self.handle(title="链接", url=url, openid=openid)
    return True

  def _try_weixin_media(
    self,
    url,
    openid=None,
    header=None,
    title=None,
    from_image_marker=False,
  ):
    """优先尝试按公众号图片页处理（只 resolve 一次）"""
    if not is_weixin_article_url(url) and not is_direct_image_url(url):
      return False
    media = WeixinMediaHandler(self.uploader, self.options)
    if is_direct_image_url(url):
      if media.handle_direct_image_url(url, openid=openid, header=header):
        logger.info("已处理直链图片: %s", url)
        return True
    if not is_weixin_article_url(url):
      return False
    timeout = self.options.get("jina_timeout", 30)
    resolved = resolve_weixin_url(url, timeout=timeout)
    if resolved and resolved.get("kind") == "images":
      media.handle_weixin_url(
        url,
        openid=openid,
        header=header,
        title=title or "图片",
        from_image_marker=from_image_marker or bool(_WEIXIN_SHORT_RE.match(url)),
        resolved=resolved,
      )
      logger.info("已处理公众号图片: %s", url)
      return True
    return False

  def _save_weixin_short_fallback(self, url, openid=None, header=None, title="链接"):
    """公众号短链无法解析时的最简笔记"""
    body_parts = []
    if header:
      body_parts.append(header)
      body_parts.append("")
    body_parts.append(f"[图片] {title}")
    body_parts.append(url)
    body_parts.append("")
    body_parts.append(_WEIXIN_FALLBACK_HINT)
    self.save_note("image", "\n".join(body_parts), openid=openid)
    logger.warning("公众号短链无法抓取，已保存链接: %s", url)

  def _fetch_full_article(self, url):
    """抓取文章全文（仅文章，不重复解析图片页）"""
    timeout = self.options.get("jina_timeout", 30)
    if is_weixin_article_url(url):
      resolved = resolve_weixin_url(url, timeout=timeout)
      if not resolved or resolved.get("kind") != "article":
        return None
      content = resolved.get("markdown")
      if content and not is_blocked_content(content):
        return content
      return None
    return self._fetch_via_jina(url, timeout=timeout)

  def _fetch_via_jina(self, url, timeout=30):
    """调用 Jina Reader API 获取 Markdown 正文"""
    jina_url = f"{JINA_READER_BASE}{url}"
    try:
      resp = requests.get(
        jina_url,
        timeout=timeout,
        headers={"Accept": "text/markdown"},
      )
      if not resp.ok:
        logger.warning("Jina 返回 HTTP %s: %s", resp.status_code, url)
        return None
      content = resp.text.strip()
      if is_blocked_content(content):
        logger.warning("Jina 返回无效内容: %s", url)
        return None
      if len(content) < 50:
        logger.warning("Jina 返回内容过短: %s", url)
        return None
      return content
    except requests.RequestException as exc:
      logger.warning("Jina 请求异常 %s: %s", url, exc)
      return None
