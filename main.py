from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
from pkg.platform.sources.wechatpad import WeChatPadAdapter
import os
import requests
from bs4 import BeautifulSoup
import re
import asyncio
import hashlib
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random
import time
from typing import Optional, List, Dict
from .qinglong_api import QingLongAPI
'''
sender_id: 发送者ID
launcher_id: 发送者群ID
'''

# 注册插件
@register(name="WechatImageDownloader", description="下载微信文章图片", version="0.3.0", author="lovefan-fan")
class WechatImageDownloader(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # self.qinglong_url = self.host.get_config("qinglong_url")
        # self.client_id = self.host.get_config("client_id")
        # self.client_secret = self.host.get_config("client_secret")
        # 配置请求会话
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # 最大重试次数
            backoff_factor=1,  # 重试间隔
            status_forcelist=[500, 502, 503, 504]  # 需要重试的HTTP状态码
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 设置默认请求头
        self.session.headers.update(self.headers)
        
        # 请求超时设置（秒）
        self.timeout = (5, 10)  # (连接超时, 读取超时)

    def calculate_md5(self, data):
        """计算数据的MD5值"""
        return hashlib.md5(data).hexdigest()

    async def forward_emoji(self, emoji_md5, to_user_name, adapter):
        """调用转发表情API"""
        if not isinstance(adapter, WeChatPadAdapter):
            self.ap.logger.error("不是 WeChatPad 适配器")
            return None
            
        try:
            return adapter.bot.send_emoji_message(
                to_wxid=to_user_name,
                emoji_md5=emoji_md5,
                emoji_size=0
            )
        except Exception as e:
            self.ap.logger.error(f"调用转发表情API失败：{str(e)}")
            return None

    async def send_text(self, to_user_name: str, content: str, adapter):
        """发送文本消息"""
        if not isinstance(adapter, WeChatPadAdapter):
            self.ap.logger.error("不是 WeChatPad 适配器")
            return None
            
        try:
            return adapter.bot.send_text_message(
                to_wxid=to_user_name,
                message=content
            )
        except Exception as e:
            self.ap.logger.error(f"发送文本消息失败：{str(e)}")
            return None

    async def handle_img_command(self, ctx: EventContext, target_id: str, msg: str):
        """处理图片命令的通用函数"""
        # 提取URL
        url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
        if not url_match:
            await self.send_text(
                to_user_name=target_id,
                content="请提供有效的微信文章链接，格式：/img 链接",
                adapter=ctx.event.query.adapter
            )
            return False

        url = url_match.group(1)
        
        try:
            response = requests.get(url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            img_tags = soup.find_all('img')
            
            if not img_tags:
                await self.send_text(
                    to_user_name=target_id,
                    content="未找到图片",
                    adapter=ctx.event.query.adapter
                )
                return False

            # 发送开始下载的消息
            await self.send_text(
                to_user_name=target_id,
                content=f"找到 {len(img_tags)} 张图片，开始处理...",
                adapter=ctx.event.query.adapter
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
                            # 计算MD5
                            emoji_md5 = self.calculate_md5(img_data)
                            
                            # 调用转发表情API
                            result = await self.forward_emoji(emoji_md5, target_id, ctx.event.query.adapter)
                            
                            if result:
                                success_count += 1
                            
                            # 等待2秒
                            await asyncio.sleep(2)
                        else:
                            self.ap.logger.error(f"下载图片失败，状态码：{img_response.status_code}")
                    except Exception as e:
                        self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
            
            # 发送完成消息
            await self.send_text(
                to_user_name=target_id,
                content=f"处理完成，成功转发 {success_count} 张图片",
                adapter=ctx.event.query.adapter
            )
            return True
            
        except Exception as e:
            self.ap.logger.error(f"处理失败：{str(e)}")
            await self.send_text(
                to_user_name=target_id,
                content=f"处理失败：{str(e)}",
                adapter=ctx.event.query.adapter
            )
            return False

    # 当收到个人消息时触发
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        wxid = ctx.event.sender_id  # 这里改名
        # 新增/小米命令逻辑
        if not hasattr(self, '_xiaomi_state'):
            self._xiaomi_state = {}
        if msg.startswith("/小米"):
            ctx.prevent_default()
            self._xiaomi_state[wxid] = {'step': 1, 'data': {}}
            await self.send_text(
                to_user_name=wxid,
                content="请发送passToken",
                adapter=ctx.event.query.adapter
            )
            return
        # 依次接收passToken、userId
        if wxid in self._xiaomi_state:
            ctx.prevent_default()
            state = self._xiaomi_state[wxid]
            if state['step'] == 1:
                state['data']['passToken'] = msg.strip()
                state['step'] = 2
                await self.send_text(
                    to_user_name=wxid,
                    content="请发送userId",
                    adapter=ctx.event.query.adapter
                )
                return
            elif state['step'] == 2:
                ctx.prevent_default()
                state['data']['userId'] = msg.strip()
                state['data']['wxid'] = wxid  # 自动获取
                # 调用青龙API
                ql = QingLongAPI(
                    self.host.get_config("qinglong_url"),
                    self.host.get_config("client_id"),
                    self.host.get_config("client_secret")
                )
                env_value = str(state['data'])
                ql.update_env('xiaomi', env_value)
                await self.send_text(
                    to_user_name=wxid,
                    content="已提交到青龙环境变量！",
                    adapter=ctx.event.query.adapter
                )
                del self._xiaomi_state[wxid]
                return
        if msg.startswith("/img"):
            # 阻止默认行为
            ctx.prevent_default()
            await self.handle_img_command(ctx, ctx.event.sender_id, msg)
            return
        
        if msg.startswith("/id"):
            ctx.prevent_default()
            await self.send_text(
                to_user_name=ctx.event.sender_id,
                content=f"你的ID是: {ctx.event.sender_id}",
                adapter=ctx.event.query.adapter
            )
            return

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/img"):
            # 阻止默认行为
            ctx.prevent_default()
            await self.handle_img_command(ctx, ctx.event.launcher_id, msg)
            return
        
        if msg.startswith("/id"):
            ctx.prevent_default()
            await self.send_text(
                to_user_name=ctx.event.launcher_id,
                content=f"你的ID是: {ctx.event.sender_id}",
                adapter=ctx.event.query.adapter
            )
            return

    # 插件卸载时触发
    def __del__(self):
        pass