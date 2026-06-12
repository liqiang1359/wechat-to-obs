# -*- coding: utf-8 -*-
"""配置文件加载模块"""

import os  # 操作系统路径
import yaml  # YAML 解析


# 默认配置文件路径（项目根目录下的 config.yaml）
DEFAULT_CONFIG_PATH = os.path.join(
  os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
  "config.yaml",
)


def load_config(config_path=None):
  """
  加载 YAML 配置文件
  :param config_path: 配置文件路径，默认使用项目根目录 config.yaml
  :return: 配置字典
  """
  # 未指定路径时使用默认路径
  path = config_path or DEFAULT_CONFIG_PATH
  # 配置文件必须存在
  if not os.path.isfile(path):
    raise FileNotFoundError(
      f"配置文件不存在: {path}，请复制 config.example.yaml 为 config.yaml 并填写"
    )
  # 以 UTF-8 读取 YAML
  with open(path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
  # 返回解析后的配置
  return config
