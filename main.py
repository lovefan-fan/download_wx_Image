from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
import os
import requests
from bs4 import BeautifulSoup
import re
import asyncio
import hashlib
import json


# 注册插件
@register(name="WechatImageDownloader", description="下载微信文章图片", version="0.2.0", author="lovefan-fan")
class MyPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    # 异步初始化
    async def initialize(self):
        pass

    def calculate_md5(self, data):
        """计算数据的MD5值"""
        return hashlib.md5(data).hexdigest()

    async def send_text(self, to_user_name: str, content: str, adapter):
        """发送文本消息"""
        data = {
            "MsgItem": [
                {
                    "AtWxIDList": [],
                    "ImageContent": "",
                    "MsgType": 1,  # 文本消息类型
                    "TextContent": content,
                    "ToUserName": to_user_name
                }
            ]
        }
        url = f"{adapter.config['wechatpad_url']}/message/SendTextMessage"
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    async def send_image(self, to_user_name: str, image_data: bytes, adapter):
        """发送图片消息"""
        emoji_md5 = self.calculate_md5(image_data)
        data = {
            "EmojiList": [
                {
                    "EmojiMd5": emoji_md5,
                    "EmojiSize": 0,
                    "ToUserName": to_user_name
                }
            ]
        }
        url = f"{adapter.config['wechatpad_url']}/message/ForwardEmoji"
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()

    # 当收到个人消息时触发
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content="请提供有效的微信文章链接，格式：/img 链接",
                    adapter=ctx.query.adapter
                )
                ctx.prevent_default()
                return

            url = url_match.group(1)
            
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                
                if not img_tags:
                    await self.send_text(
                        to_user_name=ctx.event.sender_id,
                        content="未找到图片",
                        adapter=ctx.query.adapter
                    )
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content=f"找到 {len(img_tags)} 张图片，开始处理...",
                    adapter=ctx.query.adapter
                )
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    if img_url and 'http' in img_url:
                        try:
                            # 下载图片
                            img_response = requests.get(img_url, headers=self.headers)
                            if img_response.status_code == 200:
                                img_data = img_response.content
                                # 发送图片
                                await self.send_image(
                                    to_user_name=ctx.event.sender_id,
                                    image_data=img_data,
                                    adapter=ctx.query.adapter
                                )
                                success_count += 1
                                # 等待2秒
                                await asyncio.sleep(2)
                            else:
                                self.ap.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content=f"处理完成，成功发送 {success_count} 张图片",
                    adapter=ctx.query.adapter
                )
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content=f"处理失败：{str(e)}",
                    adapter=ctx.query.adapter
                )
                return

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content="请提供有效的微信文章链接，格式：/img 链接",
                    adapter=ctx.query.adapter
                )
                ctx.prevent_default()
                return

            url = url_match.group(1)
            
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                
                if not img_tags:
                    await self.send_text(
                        to_user_name=ctx.event.room_id,
                        content="未找到图片",
                        adapter=ctx.query.adapter
                    )
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content=f"找到 {len(img_tags)} 张图片，开始处理...",
                    adapter=ctx.query.adapter
                )
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    if img_url and 'http' in img_url:
                        try:
                            # 下载图片
                            img_response = requests.get(img_url, headers=self.headers)
                            if img_response.status_code == 200:
                                img_data = img_response.content
                                # 发送图片
                                await self.send_image(
                                    to_user_name=ctx.event.room_id,
                                    image_data=img_data,
                                    adapter=ctx.query.adapter
                                )
                                success_count += 1
                                # 等待2秒
                                await asyncio.sleep(2)
                            else:
                                self.ap.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content=f"处理完成，成功发送 {success_count} 张图片",
                    adapter=ctx.query.adapter
                )
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content=f"处理失败：{str(e)}",
                    adapter=ctx.query.adapter
                )
                return

    # 插件卸载时触发
    def __del__(self):
        pass
