# -*- coding: utf-8 -*-
"""微信公众号文章抓取（绕过 Jina 对 mp.weixin.qq.com 的验证页问题）"""

import re  # 正则提取
import html as html_lib  # HTML 实体解码
import logging  # 日志
import requests  # HTTP 请求


logger = logging.getLogger(__name__)  # 模块日志

# 模拟微信内置浏览器 User-Agent
_WEIXIN_UA = (
  "Mozilla/5.0 (Linux; Android 12; SM-G9980) AppleWebKit/537.36 "
  "(KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.99 "
  "Mobile Safari/537.36 MicroMessenger/8.0.32.2300(0x28002051) "
  "Process/tools WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64"
)
# 微信公众号域名
_WEIXIN_HOST = "mp.weixin.qq.com"
# 抓取失败时的典型关键词
_BLOCKED_MARKERS = (
  "环境异常",
  "完成验证后即可继续访问",
  "Weixin Official Accounts Platform",
  "去验证",
)
# 从 HTML 提取标题
_TITLE_PATTERNS = (
  re.compile(r'property="og:title"\s+content="([^"]*)"', re.I),
  re.compile(r"<title>([^<]*)</title>", re.I),
  re.compile(r"var\s+msg_title\s*=\s*['\"]([^'\"]*)['\"]", re.I),
)
# 正文容器
_CONTENT_PATTERN = re.compile(
  r'id="js_content"[^>]*>(.*?)</div>\s*<script',
  re.DOTALL | re.I,
)


def is_weixin_article_url(url):
  """判断是否为微信公众号文章链接"""
  return _WEIXIN_HOST in (url or "")


def is_blocked_content(text):
  """
  判断抓取结果是否为微信验证页或 Jina 无效内容
  :param text: 抓取到的正文
  :return: True 表示内容无效
  """
  if not text or len(text.strip()) < 80:
    return True
  sample = text.strip()
  hit_count = sum(1 for marker in _BLOCKED_MARKERS if marker in sample)
  if hit_count >= 2:
    return True
  if "环境异常" in sample and "验证" in sample:
    return True
  if sample.startswith("Title:") and "Markdown Content:" in sample:
    if "环境异常" in sample or "Weixin Official Accounts Platform" in sample:
      return True
  return False


def fetch_weixin_article(url, timeout=30):
  """
  直接请求公众号文章页并解析正文
  :param url: 文章 URL
  :param timeout: 超时秒数
  :return: Markdown 字符串，失败返回 None
  """
  try:
    resp = requests.get(
      url,
      timeout=timeout,
      headers={
        "User-Agent": _WEIXIN_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9",
      },
      allow_redirects=True,
    )
    if not resp.ok:
      logger.warning("公众号页面 HTTP %s: %s", resp.status_code, url)
      return None
    page_html = resp.text
    if "环境异常" in page_html and "验证" in page_html:
      logger.warning("公众号返回验证页，服务器 IP 可能被微信限制: %s", url)
      return None
    title = _extract_title(page_html)
    content_html = _extract_content_html(page_html)
    if not content_html:
      logger.warning("未解析到 js_content: %s", url)
      return None
    body_md = _html_to_markdown(content_html)
    if not body_md or len(body_md) < 30:
      logger.warning("公众号正文过短: %s", url)
      return None
    parts = []
    if title:
      parts.append(f"# {title.strip()}")
      parts.append("")
    parts.append(body_md)
    result = "\n".join(parts).strip()
    if is_blocked_content(result):
      return None
    return result
  except requests.RequestException as exc:
    logger.warning("公众号请求异常 %s: %s", url, exc)
    return None


def _extract_title(page_html):
  """从 HTML 中提取文章标题"""
  for pattern in _TITLE_PATTERNS:
    match = pattern.search(page_html)
    if match:
      title = html_lib.unescape(match.group(1)).strip()
      if title and title not in ("Weixin Official Accounts Platform", "微信公众平台"):
        return title
  return ""


def _extract_content_html(page_html):
  """提取 id=js_content 内的 HTML"""
  match = _CONTENT_PATTERN.search(page_html)
  if match:
    return match.group(1)
  fallback = re.search(r'id="js_content"[^>]*>(.*)', page_html, re.DOTALL | re.I)
  if fallback:
    raw = fallback.group(1)
    end = raw.lower().find("</div>")
    return raw[:end] if end > 0 else raw
  return ""


def _html_to_markdown(content_html):
  """将公众号正文 HTML 粗略转为 Markdown"""
  text = content_html
  text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
  text = re.sub(r"</p>\s*", "\n\n", text, flags=re.I)
  text = re.sub(r"</section>\s*", "\n\n", text, flags=re.I)
  text = re.sub(r"</h[1-6]>\s*", "\n\n", text, flags=re.I)

  def _img_replace(match):
    tag = match.group(0)
    src_match = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', tag, re.I)
    if src_match:
      return f"\n![]({src_match.group(1)})\n"
    return ""

  text = re.sub(r"<img[^>]+>", _img_replace, text, flags=re.I)
  text = re.sub(r"<[^>]+>", "", text)
  text = html_lib.unescape(text)
  text = re.sub(r"\n{3,}", "\n\n", text)
  return text.strip()
