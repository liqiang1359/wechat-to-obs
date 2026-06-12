# -*- coding: utf-8 -*-
"""本地临时文件目录管理"""

import os  # 路径操作
import tempfile  # 系统临时目录


# 项目内临时目录名
TMP_DIR_NAME = "tmp"


def get_tmp_dir():
  """
  获取项目 tmp 目录路径，不存在则创建
  :return: 绝对路径字符串
  """
  # 项目根目录 = utils 的上一级
  root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  # tmp 子目录
  tmp_dir = os.path.join(root, TMP_DIR_NAME)
  # 确保目录存在
  os.makedirs(tmp_dir, exist_ok=True)
  return tmp_dir


def write_temp_file(content, filename, binary=False):
  """
  将内容写入临时文件
  :param content: 文本字符串或二进制 bytes
  :param filename: 文件名
  :param binary: 是否二进制写入
  :return: 本地临时文件绝对路径
  """
  # 获取临时目录
  tmp_dir = get_tmp_dir()
  # 完整路径
  path = os.path.join(tmp_dir, filename)
  # 按模式写入
  mode = "wb" if binary else "w"
  encoding = None if binary else "utf-8"
  with open(path, mode, encoding=encoding) as f:
    f.write(content)
  return path


def write_temp_bytes(data, filename):
  """
  将二进制数据写入临时文件
  :param data: bytes
  :param filename: 文件名
  :return: 本地路径
  """
  return write_temp_file(data, filename, binary=True)
