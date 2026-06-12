# -*- coding: utf-8 -*-
import re
import requests

url = "https://mp.weixin.qq.com/s/9FF64ADZnb--PrIPKWzrKA"
ua = (
  "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
  "MicroMessenger/8.0.32 NetType/WIFI Language/zh_CN"
)
r = requests.get(url, headers={"User-Agent": ua}, timeout=20, allow_redirects=True)
html = r.text
idx = html.find('id="js_content"')
print("idx", idx)
if idx >= 0:
  snippet = html[idx:idx+800]
  print(snippet)
# find js_content closing - look for rich_media_content
for m in re.finditer(r'id="js_content"[^>]*>', html):
  start = m.end()
  # count div depth
  depth = 1
  i = start
  while i < len(html) and depth > 0:
    if html.startswith("<div", i):
      depth += 1
    elif html.startswith("</div>", i):
      depth -= 1
    i += 1
  chunk = html[start:i-6]
  print("depth parse len", len(chunk))
  print("chunk preview", chunk[:300])
  break
