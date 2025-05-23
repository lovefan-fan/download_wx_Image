from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
from pkg.platform.types import Image  # 添加 Image 类的导入
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
        self.image_dir = None

    # 异步初始化
    async def initialize(self):
        self.image_dir = os.path.join(os.getcwd(), 'wechat_images')
        os.makedirs(self.image_dir, exist_ok=True)
        self.ap.logger.info(f"图片保存目录：{self.image_dir}")

    def get_file_extension(self, url):
        try:
            # 从URL中获取文件扩展名
            response = requests.head(url, headers=self.headers)
            content_type = response.headers.get('content-type', '')
            self.ap.logger.info(f"图片URL: {url}, Content-Type: {content_type}")
            
            if 'gif' in content_type:
                return '.gif'
            elif 'png' in content_type:
                return '.png'
            elif 'jpeg' in content_type or 'jpg' in content_type:
                return '.jpg'
            else:
                return '.jpg'  # 默认使用jpg
        except Exception as e:
            self.ap.logger.error(f"获取文件扩展名失败：{url}，错误：{e}")
            return '.jpg'

    async def download_and_save_image(self, img_url, idx):
        try:
            self.ap.logger.info(f"开始下载图片：{img_url}")
            response = requests.get(img_url, headers=self.headers)
            if response.status_code != 200:
                self.ap.logger.error(f"下载图片失败，状态码：{response.status_code}")
                return None, None, None
                
            img_data = response.content
            if not img_data:
                self.ap.logger.error("下载的图片数据为空")
                return None, None, None
                
            # 获取正确的文件扩展名
            ext = self.get_file_extension(img_url)
            file_path = os.path.join(self.image_dir, f'image_{idx}{ext}')
            
            self.ap.logger.info(f"保存图片到：{file_path}")
            with open(file_path, 'wb') as f:
                f.write(img_data)
            
            # 验证文件是否成功保存
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                self.ap.logger.info(f"图片保存成功，大小：{file_size} 字节")
                return img_data, ext, file_path
            else:
                self.ap.logger.error("图片文件保存失败")
                return None, None, None
                
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
            self.ap.logger.info(f"收到图片下载请求，URL: {url}")
            
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
                    self.ap.logger.info(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        result = await self.download_and_save_image(img_url, idx)
                        if result:
                            img_data, ext, file_path = result
                            try:
                                # 使用文件路径发送图片
                                self.ap.logger.info(f"尝试发送图片：{file_path}")
                                await ctx.reply(MessageChain([Image(path=file_path)]))
                                success_count += 1
                                self.ap.logger.info(f"成功发送第 {idx+1} 张图片，格式：{ext}")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"下载完成，成功下载并发送 {success_count} 张图片"]))
                
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
            self.ap.logger.info(f"收到图片下载请求，URL: {url}")
            
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
                    self.ap.logger.info(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        result = await self.download_and_save_image(img_url, idx)
                        if result:
                            img_data, ext, file_path = result
                            try:
                                # 使用文件路径发送图片
                                self.ap.logger.info(f"尝试发送图片：{file_path}")
                                await ctx.reply(MessageChain([Image(path=file_path)]))
                                success_count += 1
                                self.ap.logger.info(f"成功发送第 {idx+1} 张图片，格式：{ext}")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送完成消息
                await ctx.reply(MessageChain([f"下载完成，成功下载并发送 {success_count} 张图片"]))
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await ctx.reply(MessageChain([f"处理失败：{str(e)}"]))
                return

    # 插件卸载时触发
    def __del__(self):
        pass
