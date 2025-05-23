from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
import os
import requests
from bs4 import BeautifulSoup
import re
import base64


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

    async def download_and_save_image(self, img_url, idx):
        try:
            img_data = requests.get(img_url, headers=self.headers).content
            file_path = f'wechat_images/image_{idx}.gif'
            with open(file_path, 'wb') as f:
                f.write(img_data)
            return img_data  # 返回图片数据而不是文件路径
        except Exception as e:
            self.ap.logger.error(f"下载失败：{img_url}，错误：{e}")
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

                ctx.add_return("reply", [f"找到 {len(img_tags)} 张图片，开始下载..."])
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    self.ap.logger.debug(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        img_data = await self.download_and_save_image(img_url, idx)
                        if img_data:
                            try:
                                # 将图片数据转换为base64
                                img_base64 = base64.b64encode(img_data).decode('utf-8')
                                # 使用MessageChain发送图片
                                await ctx.reply(MessageChain([Image(base64=img_base64)]))
                                success_count += 1
                                self.ap.logger.debug(f"成功发送第 {idx+1} 张图片")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                ctx.add_return("reply", [f"下载完成，成功下载并发送 {success_count} 张图片"])
                ctx.prevent_default()
                
            except Exception as e:
                ctx.add_return("reply", [f"处理失败：{str(e)}"])
                ctx.prevent_default()
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

                ctx.add_return("reply", [f"找到 {len(img_tags)} 张图片，开始下载..."])
                
                success_count = 0
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    self.ap.logger.debug(f"处理第 {idx+1} 张图片，URL: {img_url}")
                    
                    if img_url and 'http' in img_url:
                        img_data = await self.download_and_save_image(img_url, idx)
                        if img_data:
                            try:
                                # 将图片数据转换为base64
                                img_base64 = base64.b64encode(img_data).decode('utf-8')
                                # 使用MessageChain发送图片
                                await ctx.reply(MessageChain([Image(base64=img_base64)]))
                                success_count += 1
                                self.ap.logger.debug(f"成功发送第 {idx+1} 张图片")
                            except Exception as e:
                                self.ap.logger.error(f"发送第 {idx+1} 张图片失败：{str(e)}")
                
                ctx.add_return("reply", [f"下载完成，成功下载并发送 {success_count} 张图片"])
                ctx.prevent_default()
                
            except Exception as e:
                ctx.add_return("reply", [f"处理失败：{str(e)}"])
                ctx.prevent_default()
                return

    # 插件卸载时触发
    def __del__(self):
        pass
