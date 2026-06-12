# -*- coding: utf-8 -*-
"""微信公众号页面解析：文章正文与图片页（picture_page）"""

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
  re.compile(r'property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', re.I),
  re.compile(r"<title>([^<]*)</title>", re.I),
  re.compile(r"var\s+msg_title\s*=\s*['\"]([^'\"]*)['\"]", re.I),
)
# 图片 CDN 域名
_IMAGE_HOST_MARKERS = ("mmbiz.qpic.cn", "wx.qlogo.cn")


def is_weixin_article_url(url):
  """判断是否为微信公众号相关链接"""
  return _WEIXIN_HOST in (url or "")


def is_direct_image_url(url):
  """判断是否为可直接下载的微信图片 URL"""
  return any(host in (url or "") for host in _IMAGE_HOST_MARKERS)


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


def fetch_page_html(url, timeout=30):
  """
  请求公众号页面 HTML
  :param url: 页面 URL
  :return: HTML 字符串，失败返回 None
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
    return resp.text
  except requests.RequestException as exc:
    logger.warning("公众号请求异常 %s: %s", url, exc)
    return None


def download_image_bytes(image_url, timeout=30):
  """
  下载微信 CDN 图片二进制
  :param image_url: 图片 URL
  :return: bytes 或 None
  """
  try:
    resp = requests.get(
      image_url,
      timeout=timeout,
      headers={
        "User-Agent": _WEIXIN_UA,
        "Referer": "https://mp.weixin.qq.com/",
      },
    )
    if not resp.ok or len(resp.content) < 200:
      logger.warning("图片下载失败 HTTP %s: %s", resp.status_code, image_url[:80])
      return None
    return resp.content
  except requests.RequestException as exc:
    logger.warning("图片下载异常 %s: %s", image_url[:80], exc)
    return None


def image_ext_from_url(url):
  """根据 URL 参数或路径猜测图片扩展名"""
  lower = (url or "").lower()
  if "wx_fmt=png" in lower or ".png" in lower:
    return ".png"
  if "wx_fmt=gif" in lower or ".gif" in lower:
    return ".gif"
  if "wx_fmt=webp" in lower or ".webp" in lower:
    return ".webp"
  return ".jpg"


def resolve_weixin_url(url, timeout=30):
  """
  解析公众号链接：文章或图片页
  :return: {"kind":"article","markdown":...} / {"kind":"images","urls":[...],"title":...} / None
  """
  page_html = fetch_page_html(url, timeout=timeout)
  if not page_html:
    return None
  if _is_verification_page(page_html):
    logger.warning("公众号返回验证页: %s", url)
    return None
  title = _extract_title(page_html)
  if _is_picture_page(page_html):
    image_urls = extract_weixin_image_urls(page_html)
    if image_urls:
      logger.info("识别为公众号图片页，共 %d 张", len(image_urls))
      return {"kind": "images", "urls": image_urls, "title": title}
  content_html = _extract_content_html(page_html)
  if content_html:
    body_md = _html_to_markdown(content_html)
    if body_md and len(body_md) >= 30:
      parts = []
      if title:
        parts.append(f"# {title.strip()}")
        parts.append("")
      parts.append(body_md)
      result = "\n".join(parts).strip()
      if not is_blocked_content(result):
        return {"kind": "article", "markdown": result}
  image_urls = extract_weixin_image_urls(page_html)
  if image_urls:
    logger.info("无 js_content，退化为图片提取，共 %d 张", len(image_urls))
    return {"kind": "images", "urls": image_urls, "title": title}
  return None


def fetch_weixin_article(url, timeout=30):
  """
  抓取公众号文章 Markdown（兼容旧调用）
  :param url: 文章 URL
  :return: Markdown 字符串，失败返回 None
  """
  resolved = resolve_weixin_url(url, timeout=timeout)
  if resolved and resolved.get("kind") == "article":
    return resolved.get("markdown")
  return None


def _is_verification_page(page_html):
  """判断是否为微信环境验证页（避免大图页误伤）"""
  if len(page_html) > 500000:
    return False
  return (
    "环境异常" in page_html
    and "完成验证后即可继续访问" in page_html
  )


def _is_picture_page(page_html):
  """判断是否为微信图片消息页（picture_page）"""
  return "picture_page" in page_html or "img_item" in page_html


def extract_weixin_image_urls(page_html):
  """
  从页面 HTML 提取微信 CDN 图片 URL
  :param page_html: 页面 HTML
  :return: 去重后的 URL 列表
  """
  urls = []
  og = re.findall(
    r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    page_html,
    re.I,
  )
  urls.extend(og)
  cdn = re.findall(r'cdn_url:\s*["\']([^"\']+)["\']', page_html)
  urls.extend(cdn)
  imgs = re.findall(
    r'(?:data-src|src)=["\']([^"\']*mmbiz\.qpic\.cn[^"\']*)["\']',
    page_html,
    re.I,
  )
  urls.extend(imgs)
  clean = []
  seen = set()
  for raw in urls:
    url = raw.replace("\\/", "/").strip()
    if "mmbiz.qpic.cn" not in url:
      continue
    if url.startswith("http://"):
      url = "https://" + url[7:]
    if url in seen:
      continue
    seen.add(url)
    clean.append(url)
  return clean


def _extract_title(page_html):
  """从 HTML 中提取页面标题"""
  for pattern in _TITLE_PATTERNS:
    match = pattern.search(page_html)
    if match:
      title = html_lib.unescape(match.group(1)).strip()
      if title and title not in ("Weixin Official Accounts Platform", "微信公众平台"):
        return title
  return ""


def _extract_content_html(page_html):
  """用 div 深度匹配提取 js_content 区域（静态 HTML 中的文章）"""
  match = re.search(r'id=["\']js_content["\'][^>]*>', page_html, re.I)
  if not match:
    return ""
  start = match.end()
  depth = 1
  pos = start
  length = len(page_html)
  while pos < length and depth > 0:
    lower = page_html[pos:pos + 6].lower()
    if lower.startswith("<div"):
      depth += 1
    elif lower.startswith("</div"):
      depth -= 1
    pos += 1
  if depth != 0:
    return ""
  return page_html[start:pos - 6]


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
