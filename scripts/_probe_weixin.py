# -*- coding: utf-8 -*-
import re
import requests
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from utils.weixin_article import _extract_content_html, _CONTENT_PATTERN, fetch_weixin_article

url = "https://mp.weixin.qq.com/s/9FF64ADZnb--PrIPKWzrKA"
ua = (
  "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
  "MicroMessenger/8.0.32 NetType/WIFI Language/zh_CN"
)
r = requests.get(url, headers={"User-Agent": ua}, timeout=20, allow_redirects=True)
html = r.text
print("pattern match", bool(_CONTENT_PATTERN.search(html)))
content = _extract_content_html(html)
print("extract len", len(content or ""))
if content:
  print("preview", content[:200])
imgs = re.findall(r'(?:data-src|src)=["\']([^"\']+mmbiz\.qpic\.cn[^"\']+)["\']', html)
print("content imgs", len(imgs))
article = fetch_weixin_article(url)
print("article", (article or "")[:300])
