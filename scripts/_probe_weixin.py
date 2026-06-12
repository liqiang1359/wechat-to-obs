# -*- coding: utf-8 -*-
import re
import requests

url = "https://mp.weixin.qq.com/s/9FF64ADZnb--PrIPKWzrKA"
ua = (
  "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
  "MicroMessenger/8.0.32 NetType/WIFI Language/zh_CN"
)
r = requests.get(url, headers={"User-Agent": ua}, timeout=20, allow_redirects=True)
h = r.text
patterns = [
  r'id=["\']js_content["\']',
  r"og:image",
  r"cdn_url",
  r"picture_page",
  r"img_item",
  r"rich_media",
]
for pat in patterns:
  print(pat, len(re.findall(pat, h, re.I)))
og = re.findall(
  r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
  h,
  re.I,
)
print("og", og[:1])
cdn = re.findall(r'cdn_url:\s*["\']([^"\']+)["\']', h)
print("cdn", cdn[:2])
mmbiz = list(dict.fromkeys(re.findall(r"https?://mmbiz\.qpic\.cn/[^\"'<>\s\\]+", h)))
print("mmbiz unique", len(mmbiz))
for u in mmbiz[:3]:
  print(" ", u[:100])
