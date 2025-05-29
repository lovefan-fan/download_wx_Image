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
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.api_url = "http://192.168.0.246:9090/message/ForwardEmoji"
        self.api_key = "10dca0e1-8c7e-41d1-8b5c-4a64b63c39cd"

    # 异步初始化
    async def initialize(self):
        pass

    def calculate_md5(self, data):
        """计算数据的MD5值"""
        return hashlib.md5(data).hexdigest()

    async def forward_emoji(self, emoji_md5, to_user_name):
        """调用转发表情API"""
        try:
            headers = {
                'accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            data = {
                "EmojiList": [
                    {
                        "EmojiMd5": emoji_md5,
                        "EmojiSize": 0,
                        "ToUserName": to_user_name
                    }
                ]
            }
            
            url = f"{self.api_url}?key={self.api_key}"
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.ap.logger.error(f"调用转发表情API失败：{str(e)}")
            return None

    # 当收到个人消息时触发
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                ctx.add_return("reply", ["请提供有效的微信文章链接，格式：/img 链接"])
                ctx.prevent_default()
                return

            url = url_match.group(1)
            
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                
                if not img_tags:
                    ctx.add_return("reply", ["未找到图片"])
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await ctx.reply(MessageChain([f"找到 {len(img_tags)} 张图片，开始处理..."]))
                
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
                                
                                # 调用转发表情API
                                to_user_name = ctx.event.sender_id  # 使用发送者ID
                                result = await self.forward_emoji(emoji_md5, to_user_name)
                                
                                if result:
                                    success_count += 1
                                else:
                                    pass
                                
                                # 等待2秒
                                await asyncio.sleep(2)
                            else:
                                self.ap.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"处理完成，成功转发 {success_count} 张图片"]))
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await ctx.reply(MessageChain([f"处理失败：{str(e)}"]))
                return

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                ctx.add_return("reply", ["请提供有效的微信文章链接，格式：/img 链接"])
                ctx.prevent_default()
                return

            url = url_match.group(1)
            
            try:
                response = requests.get(url, headers=self.headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                img_tags = soup.find_all('img')
                
                if not img_tags:
                    ctx.add_return("reply", ["未找到图片"])
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await ctx.reply(MessageChain([f"找到 {len(img_tags)} 张图片，开始处理..."]))
                
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
                                
                                # 调用转发表情API
                                to_user_name = ctx.event.launcher_id
                                result = await self.forward_emoji(emoji_md5, to_user_name)
                                
                                if result:
                                    success_count += 1
                                else:
                                    pass
                                
                                # 等待2秒
                                await asyncio.sleep(2)
                            else:
                                self.ap.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"处理完成，成功转发 {success_count} 张图片"]))
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await ctx.reply(MessageChain([f"处理失败：{str(e)}"]))
                return

    # 插件卸载时触发
    def __del__(self):
        pass
