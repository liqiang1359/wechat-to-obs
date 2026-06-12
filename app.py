# -*- coding: utf-8 -*-
"""WechatToObs Flask 入口：接收微信 Webhook 并分发消息处理"""

import io  # 标准流包装
import sys  # 平台检测
import time  # 消息去重时间戳
import threading  # 异步处理与去重锁
import logging  # 日志
from flask import Flask, request  # Web 框架
from wechatpy import parse_message  # 解析微信 XML 消息
from wechatpy.exceptions import InvalidSignatureException  # 签名校验异常
from wechatpy.utils import check_signature  # 微信签名校验
from wechatpy import WeChatClient  # 微信 API 客户端

from utils.config import load_config  # 加载配置
from utils.webdav import WebDAVUploader  # WebDAV 上传
from utils.batch import get_note_batcher  # 全局消息合并器
from handlers.text import TextHandler  # 文字处理
from handlers.link import LinkHandler  # 链接处理
from handlers.file import FileHandler  # 媒体处理
from handlers.chat import ChatHandler  # 聊天记录处理


def _ensure_utf8_stdio():
  """Windows 控制台 UTF-8 输出，避免中文乱码（仅主进程启动时调用）"""
  if sys.platform == "win32":
    if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
      sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if getattr(sys.stderr, "encoding", "").lower() != "utf-8":
      sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 配置根日志
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)  # 应用日志

# 加载配置文件
CONFIG = load_config()
# Flask 应用实例
app = Flask(__name__)
# 延迟初始化的全局单例缓存
_uploader = None
_wechat_client = None
# 微信 Token（签名校验用）
WECHAT_TOKEN = CONFIG["wechat"]["token"]
# 业务选项
OPTIONS = CONFIG["options"]
# 启动时初始化全局合并器（5 分钟窗口、note_author 等）
get_note_batcher(OPTIONS)
# 已处理 MsgId 缓存（防止微信超时重试导致重复写入）
_seen_msg_ids = {}
_seen_msg_lock = threading.Lock()
_MSG_ID_TTL = 600  # MsgId 去重保留 10 分钟


def get_uploader():
  """获取 WebDAV 上传器单例（首次调用时初始化）"""
  global _uploader
  if _uploader is None:
    _uploader = WebDAVUploader(CONFIG["webdav"], CONFIG["options"])
  return _uploader


def get_wechat_client():
  """获取微信 API 客户端单例（首次调用时初始化）"""
  global _wechat_client
  if _wechat_client is None:
    _wechat_client = WeChatClient(
      CONFIG["wechat"]["app_id"],
      CONFIG["wechat"]["app_secret"],
    )
  return _wechat_client


@app.route("/wechat", methods=["GET", "POST"])
def wechat_webhook():
  """微信服务器回调：GET 验证 URL，POST 接收消息"""
  # GET：微信验证服务器 URL
  if request.method == "GET":
    return _verify_url()
  # POST：处理用户转发的消息
  return _handle_message()


def _verify_url():
  """校验签名并返回 echostr（微信接入验证）"""
  signature = request.args.get("signature", "")
  timestamp = request.args.get("timestamp", "")
  nonce = request.args.get("nonce", "")
  echostr = request.args.get("echostr", "")
  try:
    # 使用 Token 校验签名
    check_signature(WECHAT_TOKEN, signature, timestamp, nonce)
    logger.info("微信 URL 验证成功")
    return echostr
  except InvalidSignatureException:
    logger.warning("微信 URL 验证失败：签名无效")
    return "invalid signature", 403


def _is_duplicate_msg(msg_id):
  """判断是否为微信重复推送的同一消息"""
  if not msg_id:
    return False
  now = time.time()
  with _seen_msg_lock:
    expired = [k for k, t in _seen_msg_ids.items() if now - t > _MSG_ID_TTL]
    for key in expired:
      del _seen_msg_ids[key]
    if msg_id in _seen_msg_ids:
      return True
    _seen_msg_ids[msg_id] = now
    return False


def _handle_message():
  """先返回 success，再异步处理，避免微信 5 秒超时重试"""
  raw_xml = request.data
  if not raw_xml:
    logger.warning("收到空 POST body")
    return "success"
  threading.Thread(
    target=_process_message,
    args=(raw_xml,),
    daemon=True,
  ).start()
  return "success"


def _process_message(raw_xml):
  """解析 XML 消息并按类型分发到对应 Handler"""
  try:
    # 先尝试从原始 XML 解析合并聊天记录
    uploader = get_uploader()
    wechat_client = get_wechat_client()
    chat_handler = ChatHandler(uploader, OPTIONS)
    if chat_handler.handle_raw_xml(raw_xml.decode("utf-8", errors="ignore")):
      return "success"
    # 使用 wechatpy 解析标准消息
    message = parse_message(raw_xml)
    msg_id = getattr(message, "id", None)
    if _is_duplicate_msg(msg_id):
      logger.info("重复消息已跳过 MsgId=%s", msg_id)
      return
    msg_type = message.type
    logger.info("收到消息类型: %s", msg_type)
    # 按 MsgType 分发
    if msg_type == "text":
      TextHandler(uploader, OPTIONS).handle(message)
    elif msg_type == "image":
      FileHandler(uploader, OPTIONS, wechat_client).handle_image(message)
    elif msg_type == "link":
      LinkHandler(uploader, OPTIONS).handle(
        title=message.title,
        url=message.url,
        description=getattr(message, "description", None),
        openid=getattr(message, "source", None),
      )
    elif msg_type == "voice":
      FileHandler(uploader, OPTIONS, wechat_client).handle_voice(message)
    elif msg_type == "video":
      FileHandler(uploader, OPTIONS, wechat_client).handle_video(message)
    elif msg_type == "shortvideo":
      FileHandler(uploader, OPTIONS, wechat_client).handle_video(message, short=True)
    elif msg_type == "news":
      # 图文消息：逐条链接处理
      link_handler = LinkHandler(uploader, OPTIONS)
      for article in message.articles:
        link_handler.handle(
          title=article.title,
          url=article.url,
          description=article.description,
          openid=getattr(message, "source", None),
        )
    elif msg_type == "event":
      # 关注/取消关注等事件，仅记录日志
      logger.info("收到事件: %s", getattr(message, "event", ""))
    else:
      # 未知类型尝试当文字或聊天记录处理
      content = getattr(message, "content", None)
      if content:
        if not chat_handler.handle_text_fallback(content):
          TextHandler(uploader, OPTIONS).handle(message)
      else:
        logger.warning("未处理的消息类型: %s", msg_type)
  except Exception as exc:
    logger.exception("处理消息时发生错误: %s", exc)


@app.route("/health", methods=["GET"])
def health():
  """健康检查接口，供 Nginx 或监控使用"""
  return {"status": "ok", "service": "wechat-to-obs"}


def main():
  """启动 Flask 开发服务器"""
  _ensure_utf8_stdio()
  host = CONFIG["server"].get("host", "0.0.0.0")
  port = CONFIG["server"].get("port", 5000)
  logger.info("WechatToObs 启动于 %s:%s", host, port)
  app.run(host=host, port=port)


if __name__ == "__main__":
  main()
