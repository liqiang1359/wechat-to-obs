# -*- coding: utf-8 -*-
"""链接消息处理器（含 Jina Reader 全文抓取）"""

import logging  # 日志
import re  # URL 提取
import requests  # HTTP 请求 Jina
from handlers.base import BaseHandler  # 基类


logger = logging.getLogger(__name__)  # 模块日志
# Jina Reader API 前缀
JINA_READER_BASE = "https://r.jina.ai/"


class LinkHandler(BaseHandler):
  """处理 link 类型及图文消息中的链接"""

  def handle(self, title, url, description=None):
    """
    处理链接卡片
    :param title: 链接标题
    :param url: 原始 URL
    :param description: 可选描述
    """
    # 规范化 URL
    url = (url or "").strip()
    title = (title or url or "未命名链接").strip()
    # frontmatter 额外字段
    extra = {"url": url, "title": title}
    # 正文起始：标题与链接
    body_parts = [url]
    # 是否抓取全文
    if self.options.get("fetch_full_article", True) and url:
      article_md = self._fetch_full_article(url)
      if article_md:
        body_parts.append("")
        body_parts.append(article_md)
      else:
        # Jina 失败时降级
        if description:
          body_parts.append("")
          body_parts.append(description)
        logger.warning("Jina 抓取失败，已降级为标题+URL: %s", url)
    elif description:
      body_parts.append("")
      body_parts.append(description)
    # 合并正文
    body = "\n".join(body_parts)
    # 保存笔记
    self.save_note("link", body, extra_fields=extra, title=title)
    logger.info("已处理链接: %s", url)

  def handle_from_text(self, text):
    """
    从纯文本中提取 URL 并按链接处理
    :param text: 可能含 URL 的文本
    """
    # 简单 URL 正则
    url_match = re.search(r"https?://[^\s\]]+", text or "")
    if url_match:
      url = url_match.group(0)
      # 第一行非 URL 部分作为标题
      lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
      title = lines[0] if lines and url not in lines[0] else url
      self.handle(title=title, url=url, description=text)
    else:
      # 无 URL 则当普通文字
      from handlers.text import TextHandler
      TextHandler(self.uploader, self.options).handle(
        type("Msg", (), {"content": text})()
      )

  def _fetch_full_article(self, url):
    """
    调用 Jina Reader API 获取 Markdown 正文
    :param url: 原始文章 URL
    :return: Markdown 字符串，失败返回 None
    """
    # Jina 请求地址
    jina_url = f"{JINA_READER_BASE}{url}"
    # 超时秒数
    timeout = self.options.get("jina_timeout", 30)
    try:
      # 发起 GET 请求
      resp = requests.get(
        jina_url,
        timeout=timeout,
        headers={"Accept": "text/markdown"},
      )
      # 非 2xx 视为失败
      if not resp.ok:
        logger.warning("Jina 返回 HTTP %s: %s", resp.status_code, url)
        return None
      # 响应正文
      content = resp.text.strip()
      # 过短内容视为无效
      if len(content) < 50:
        logger.warning("Jina 返回内容过短: %s", url)
        return None
      return content
    except requests.RequestException as exc:
      # 网络或超时异常
      logger.warning("Jina 请求异常 %s: %s", url, exc)
      return None
