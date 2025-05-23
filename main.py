from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
import os
import requests
from bs4 import BeautifulSoup
import re
import base64
import mimetypes


# 注册插件
@register(name="WechatImageDownloader", description="下载微信文章图片", version="0.2", author="lovefan-fan")
class MyPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        os.makedirs('wechat_images', exist_ok=True)

    # 异步初始化
    async def initialize(self):
        pass

    def get_file_extension(self, url):
        # 从URL中获取文件扩展名
        content_type = requests.head(url, headers=self.headers).headers.get('content-type', '')
        if 'gif' in content_type:
            return '.gif'
        elif 'png' in content_type:
            return '.png'
        elif 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        else:
            return '.jpg'  # 默认使用jpg

    async def download_and_save_image(self, img_url, idx):
        try:
            response = requests.get(img_url, headers=self.headers)
            img_data = response.content
            # 获取正确的文件扩展名
            ext = self.get_file_extension(img_url)
            file_path = f'wechat_images/image_{idx}{ext}'
            with open(file_path, 'wb') as f:
                f.write(img_data)
            return img_data, ext, file_path  # 返回图片数据、扩展名和文件路径
        except Exception as e:
            self.ap.logger.error(f"下载失败：{img_url}，错误：{e}")
            return None, None, None

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
                await ctx.reply(MessageChain([f"找到 {len(img_tags)} 张图片，开始下载..."]))
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    self.ap.logger.debug(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        result = await self.download_and_save_image(img_url, idx)
                        if result:
                            img_data, ext, file_path = result
                            try:
                                # 使用文件路径发送图片
                                ctx.add_return("image", [file_path])
                                success_count += 1
                                self.ap.logger.debug(f"成功发送第 {idx+1} 张图片，格式：{ext}")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"下载完成，成功下载并发送 {success_count} 张图片"]))
                
            except Exception as e:
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
                await ctx.reply(MessageChain([f"找到 {len(img_tags)} 张图片，开始下载..."]))
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    self.ap.logger.debug(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        result = await self.download_and_save_image(img_url, idx)
                        if result:
                            img_data, ext, file_path = result
                            try:
                                # 使用文件路径发送图片
                                ctx.add_return("image", [file_path])
                                success_count += 1
                                self.ap.logger.debug(f"成功发送第 {idx+1} 张图片，格式：{ext}")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"下载完成，成功下载并发送 {success_count} 张图片"]))
                
            except Exception as e:
                await ctx.reply(MessageChain([f"处理失败：{str(e)}"]))
                return

    # 插件卸载时触发
    def __del__(self):
        pass
