# plugins/GroupInsight/__init__.py

from .main import WechatImageDownloaderPlugin

# 遵循 LangBot 的插件加载机制，确保插件类被暴露
__all__ = ["WechatImageDownloaderPlugin"]