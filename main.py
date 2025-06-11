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


# 注册插件
@register(name="WechatImageDownloader", description="下载微信文章图片", version="0.2.0", author="lovefan-fan")
class MyPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        super().__init__(host)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 邮件相关配置
        self.temp_mail_api = "https://tempmail.plus/api"
        self.email_address = "aafob@mailto.plus"  # 临时邮箱地址
        self.last_mail_id = None  # 用于记录最后处理的邮件ID
        
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

    def make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """统一的请求处理方法，包含重试和超时机制"""
        try:
            # 添加超时设置
            kwargs['timeout'] = self.timeout
            # 确保使用配置的请求头
            if 'headers' not in kwargs:
                kwargs['headers'] = self.headers
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.ap.logger.error(f"请求失败 ({method} {url}): {str(e)}")
            return None

    def delete_email(self, mail_id: int) -> bool:
        """删除指定ID的邮件"""
        try:
            url = f"{self.temp_mail_api}/mails/{mail_id}"
            params = {
                "email": self.email_address,
                "epin": ""
            }
            
            response = self.make_request("DELETE", url, params=params)
            if response:
                data = response.json()
                return data.get("result", False)
            return False
            
        except Exception as e:
            self.ap.logger.error(f"删除邮件时出错: {str(e)}")
            return False

    def get_email_content(self, mail_id: int) -> Optional[Dict]:
        """获取邮件详细内容"""
        try:
            url = f"{self.temp_mail_api}/mails/{mail_id}"
            params = {
                "email": self.email_address,
                "epin": ""
            }
            
            response = self.make_request("GET", url, params=params)
            if response:
                data = response.json()
                if not data.get("result"):
                    self.ap.logger.error(f"获取邮件内容失败: {mail_id}")
                    return None
                return data
            return None
            
        except Exception as e:
            self.ap.logger.error(f"获取邮件内容时出错: {str(e)}")
            return None

    def get_email(self) -> Optional[List[Dict]]:
        """从tempmail.plus获取邮件列表，返回新邮件列表"""
        try:
            url = f"{self.temp_mail_api}/mails"
            params = {
                "email": self.email_address,
                "limit": 20,
                "epin": ""
            }
            
            response = self.make_request("GET", url, params=params)
            if response:
                data = response.json()
                if not data.get("result"):
                    self.ap.logger.error("获取邮件列表失败")
                    return None
                    
                mail_list = data.get("mail_list", [])
                new_mails = []
                
                for mail in mail_list:
                    # 只处理新邮件
                    if mail.get("is_new") and (self.last_mail_id is None or mail.get("mail_id") > self.last_mail_id):
                        new_mails.append(mail)
                        if self.last_mail_id is None or mail.get("mail_id") > self.last_mail_id:
                            self.last_mail_id = mail.get("mail_id")
                
                return new_mails if new_mails else None
            return None
            
        except Exception as e:
            self.ap.logger.error(f"获取邮件时出错: {str(e)}")
            return None

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

    # 当收到个人消息时触发
    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/mail"):
            # 阻止默认行为
            ctx.prevent_default()
            
            try:
                # 获取新邮件
                new_mails = self.get_email()
                
                if not new_mails:
                    await self.send_text(
                        to_user_name=ctx.event.sender_id,
                        content="没有收到新邮件",
                        adapter=ctx.event.query.adapter
                    )
                    return
                
                # 处理每封新邮件
                for mail in new_mails:
                    mail_id = mail.get("mail_id")
                    # 获取邮件详细内容
                    mail_content = self.get_email_content(mail_id)
                    
                    if mail_content:
                        # 构建消息内容
                        mail_info = f"发件人: {mail_content.get('from_name', '未知')} <{mail_content.get('from_mail', '未知')}>\n"
                        mail_info += f"主题: {mail_content.get('subject', '无主题')}\n"
                        mail_info += f"时间: {mail_content.get('date', '未知')}\n"
                        mail_info += f"内容:\n{mail_content.get('text', '无内容')}"
                        
                        # 发送邮件内容
                        await self.send_text(
                            to_user_name=ctx.event.sender_id,
                            content=mail_info,
                            adapter=ctx.event.query.adapter
                        )
                        
                        # 删除已处理的邮件
                        if self.delete_email(mail_id):
                            self.ap.logger.info(f"邮件删除成功: {mail_id}")
                        else:
                            self.ap.logger.error(f"邮件删除失败: {mail_id}")
                            
                        # 等待2秒，避免消息发送太快
                        await asyncio.sleep(2)
                
            except Exception as e:
                self.ap.logger.error(f"处理邮件时出错: {str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content=f"处理邮件时出错: {str(e)}",
                    adapter=ctx.event.query.adapter
                )
            return
            
        elif msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content="请提供有效的微信文章链接，格式：/img 链接",
                    adapter=ctx.event.query.adapter
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
                        adapter=ctx.event.query.adapter
                    )
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
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
                                to_user_name = ctx.event.sender_id  # 使用发送者ID
                                result = await self.forward_emoji(emoji_md5, to_user_name, ctx.event.query.adapter)
                                
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
                    to_user_name=ctx.event.sender_id,
                    content=f"处理完成，成功转发 {success_count} 张图片",
                    adapter=ctx.event.query.adapter
                )
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.sender_id,
                    content=f"处理失败：{str(e)}",
                    adapter=ctx.event.query.adapter
                )
                return

    # 当收到群消息时触发
    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        msg = ctx.event.text_message
        
        if msg.startswith("/mail"):
            # 阻止默认行为
            ctx.prevent_default()
            
            try:
                # 获取新邮件
                new_mails = self.get_email()
                
                if not new_mails:
                    await self.send_text(
                        to_user_name=ctx.event.room_id,
                        content="没有收到新邮件",
                        adapter=ctx.event.query.adapter
                    )
                    return
                
                # 处理每封新邮件
                for mail in new_mails:
                    mail_id = mail.get("mail_id")
                    # 获取邮件详细内容
                    mail_content = self.get_email_content(mail_id)
                    
                    if mail_content:
                        # 构建消息内容
                        mail_info = f"发件人: {mail_content.get('from_name', '未知')} <{mail_content.get('from_mail', '未知')}>\n"
                        mail_info += f"主题: {mail_content.get('subject', '无主题')}\n"
                        mail_info += f"时间: {mail_content.get('date', '未知')}\n"
                        mail_info += f"内容:\n{mail_content.get('text', '无内容')}"
                        
                        # 发送邮件内容
                        await self.send_text(
                            to_user_name=ctx.event.room_id,
                            content=mail_info,
                            adapter=ctx.event.query.adapter
                        )
                        
                        # 删除已处理的邮件
                        if self.delete_email(mail_id):
                            self.ap.logger.info(f"邮件删除成功: {mail_id}")
                        else:
                            self.ap.logger.error(f"邮件删除失败: {mail_id}")
                            
                        # 等待2秒，避免消息发送太快
                        await asyncio.sleep(2)
                
            except Exception as e:
                self.ap.logger.error(f"处理邮件时出错: {str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content=f"处理邮件时出错: {str(e)}",
                    adapter=ctx.event.query.adapter
                )
            return
            
        elif msg.startswith("/img"):
            # 提取URL
            url_match = re.search(r'/img\s*(https?://[^\s]+)', msg)
            if not url_match:
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content="请提供有效的微信文章链接，格式：/img 链接",
                    adapter=ctx.event.query.adapter
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
                        adapter=ctx.event.query.adapter
                    )
                    ctx.prevent_default()
                    return

                # 先阻止默认行为
                ctx.prevent_default()
                
                # 发送开始下载的消息
                await self.send_text(
                    to_user_name=ctx.event.room_id,
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
                                to_user_name = ctx.event.room_id
                                result = await self.forward_emoji(emoji_md5, to_user_name, ctx.event.query.adapter)
                                
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
                    to_user_name=ctx.event.room_id,
                    content=f"处理完成，成功转发 {success_count} 张图片",
                    adapter=ctx.event.query.adapter
                )
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await self.send_text(
                    to_user_name=ctx.event.room_id,
                    content=f"处理失败：{str(e)}",
                    adapter=ctx.event.query.adapter
                )
                return

    # 插件卸载时触发
    def __del__(self):
        pass