# -*- coding: utf-8 -*-
"""链接消息处理器（含 Jina Reader 全文抓取）"""

import logging  # 日志
import re  # URL 提取
import requests  # HTTP 请求 Jina
from handlers.base import BaseHandler  # 基类


logger = logging.getLogger(__name__)  # 模块日志
# Jina Reader API 前缀
JINA_READER_BASE = "https://r.jina.ai/"
# 从纯文本提取 URL
_URL_RE = re.compile(r"https?://[^\s\]\)】]+")


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
    """
    处理链接卡片或微信 [链接] 转发
    :param title: 链接标题
    :param url: 原始 URL
    :param description: 可选描述（降级备用）
    :param openid: 微信用户 OpenID（合并窗口用）
    :param header: 可选首行（如「无水的鱼    2026年06月12日 14:41」）
    :param from_link_marker: 是否来自微信 [链接] 转发格式
    """
    url = (url or "").strip()
    title = (title or url or "未命名链接").strip()
    body_parts = []
    if header:
      body_parts.append(header)
      body_parts.append("")
    if from_link_marker:
      body_parts.append(f"[链接] {title}")
    else:
      body_parts.append(title)
    body_parts.append(url)
    if self.options.get("fetch_full_article", True) and url:
      article_md = self._fetch_full_article(url)
      if article_md:
        body_parts.append("")
        body_parts.append(article_md)
      else:
        if description:
          body_parts.append("")
          body_parts.append(description)
        logger.warning("Jina 抓取失败，已降级为标题+URL: %s", url)
    elif description:
      body_parts.append("")
      body_parts.append(description)
    body = "\n".join(body_parts)
    self.save_note("link", body, openid=openid)
    logger.info("已处理链接: %s", url)

  def handle_from_text(self, text, openid=None):
    """
    从纯文本中提取 [链接] 或 URL 并按链接处理
    :param text: 可能含 [链接] 或 URL 的文本
    :param openid: 微信用户 OpenID
    """
    from utils.markdown import parse_wechat_shared_link

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
    if url_match:
      url = url_match.group(0).rstrip(".,;)")
      lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
      title = lines[0] if lines and url not in lines[0] else url
      self.handle(title=title, url=url, description=text, openid=openid)
      return True
    return False

  def _fetch_full_article(self, url):
    """
    调用 Jina Reader API 获取 Markdown 正文
    :param url: 原始文章 URL
    :return: Markdown 字符串，失败返回 None
    """
    jina_url = f"{JINA_READER_BASE}{url}"
    timeout = self.options.get("jina_timeout", 30)
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
      if len(content) < 50:
        logger.warning("Jina 返回内容过短: %s", url)
        return None
      return content
    except requests.RequestException as exc:
      logger.warning("Jina 请求异常 %s: %s", url, exc)
      return None
