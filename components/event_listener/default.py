from __future__ import annotations

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message

import os
import re
import requests
from bs4 import BeautifulSoup
import asyncio
import hashlib
import base64
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

# 添加项目根目录到Python路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in os.path.sys.path:
    os.path.sys.path.insert(0, project_root)

from . import message_processor


class DefaultEventListener(EventListener):

    async def initialize(self):
        await super().initialize()

        # 配置请求会话
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        self.timeout = (5, 10)

        # 分别处理私聊和群聊消息
        @self.handler(events.PersonMessageReceived)
        async def handle_private_message(event_context: context.EventContext):
            await self.process_message(event_context, is_private=True)
            
        @self.handler(events.GroupMessageReceived)
        async def handle_group_message(event_context: context.EventContext):
            await self.process_message(event_context, is_private=False)

    def calculate_md5(self, data):
        """计算数据的MD5值"""
        return hashlib.md5(data).hexdigest()

    async def process_message(self, event_context: context.EventContext, is_private: bool):
        """处理消息的通用函数"""
        # 获取消息内容
        message_chain = event_context.event.message_chain
        msg = "".join(
            element.text for element in message_chain
            if isinstance(element, platform_message.Plain)
        ).strip()
        
        # 获取发送者ID和群ID
        sender_id = str(event_context.event.sender_id)
        target_id = sender_id if is_private else str(event_context.event.launcher_id)

        # /img 命令
        if msg.startswith("/img"):
            event_context.prevent_default()
            await self.handle_img_command(event_context, target_id, msg)
            return

        # /id 命令
        if msg.startswith("/id"):
            event_context.prevent_default()
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"你的ID是: {sender_id}")
                ])
            )
            return

    async def handle_img_command(self, event_context: context.EventContext, target_id: str, msg: str):
        """处理图片命令的通用函数"""
        # 提取URL
        url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
        if not url_match:
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text="请提供有效的微信文章链接，格式：/img 链接")
                ])
            )
            return

        url = url_match.group(1)
        
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img')
            
            if not img_tags:
                await event_context.reply(
                    platform_message.MessageChain([
                        platform_message.Plain(text="未找到图片")
                    ])
                )
                return

            # 发送开始下载的消息
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"找到 {len(img_tags)} 张图片，开始处理...")
                ])
            )
            
            # 下载图片并一张一张发送
            success_count = 0
            for idx, img in enumerate(img_tags):
                img_url = img.get('data-src') or img.get('src')
                if img_url and 'http' in img_url:
                    try:
                        # 下载图片
                        img_response = requests.get(img_url, headers=self.headers)
                        if img_response.status_code == 200:
                            img_data = img_response.content
                            
                            # 计算MD5
                            emoji_md5 = self.calculate_md5(img_data)
                            
                            # 发送表情（使用MD5）
                            await event_context.reply(
                                platform_message.MessageChain([
                                    platform_message.WeChatEmoji(
                                        emoji_md5=emoji_md5,
                                        emoji_size=0
                                    )
                                ])
                            )
                            
                            success_count += 1
                            
                            # 等待2秒
                            await asyncio.sleep(2)
                        else:
                            self.plugin.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                    except Exception as e:
                        self.plugin.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
            
            # 发送完成消息
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"处理完成，成功发送 {success_count} 张图片")
                ])
            )
            
        except Exception as e:
            self.plugin.logger.error(f"处理失败：{str(e)}")
            await event_context.reply(
                platform_message.MessageChain([
                    platform_message.Plain(text=f"处理失败：{str(e)}")
                ])
            )
