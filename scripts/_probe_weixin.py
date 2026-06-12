# -*- coding: utf-8 -*-
import re
import requests

url = "https://mp.weixin.qq.com/s/9FF64ADZnb--PrIPKWzrKA"
ua = (
  "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
  "MicroMessenger/8.0.32 NetType/WIFI Language/zh_CN"
)
r = requests.get(url, headers={"User-Agent": ua}, timeout=20, allow_redirects=True)
print("status", r.status_code, "len", len(r.text))
print("final", r.url[:100])
for pat in ["js_content", "og:image", "mmbiz.qpic", "img_content", "picture"]:
  print(pat, bool(re.search(pat, r.text, re.I)))
og = re.findall(r'property="og:image"\s+content="([^"]+)"', r.text)
print("og:image", og[:2])
mmbiz = re.findall(r"https?://mmbiz\.qpic\.cn/[^\"'<>\s]+", r.text)
print("mmbiz count", len(mmbiz))
if mmbiz:
  print("first", mmbiz[0][:120])
