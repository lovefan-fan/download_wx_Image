from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *  # 导入事件类
from pkg.platform.types import *
import os
import requests
from bs4 import BeautifulSoup
import re


# 注册插件
@register(name="WechatImageDownloader", description="下载微信文章图片", version="0.2", author="lovefan-fan")
class MyPlugin(BasePlugin):

    # 插件加载时触发
    def __init__(self, host: APIHost):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    # 异步初始化
    async def initialize(self):
        pass

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
            #self.ap.logger.info(f"收到图片下载请求，URL: {url}")
            
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
                
                # 构建消息链
                msg_chain = MessageChain([])
                success_count = 0
                
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    if img_url and 'http' in img_url:
                        try:
                            #self.ap.logger.info(f"处理第 {idx+1} 张图片，URL: {img_url}")
                            msg_chain.append(Image(url=img_url))
                            success_count += 1
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送所有图片
                if success_count > 0:
                    self.ap.logger.info(f"msg_chain:{msg_chain}")
                    await ctx.reply(msg_chain)
                    await ctx.reply(MessageChain([f"处理完成，成功发送 {success_count} 张图片"]))
                else:
                    await ctx.reply(MessageChain(["未找到可用的图片"]))
                
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
                await ctx.reply(MessageChain([f"找到 {len(img_tags)} 张图片，开始处理..."]))
                
                # 构建消息链
                msg_chain = MessageChain([])
                success_count = 0
                
                for idx, img in enumerate(img_tags):
                    img_url = img.get('data-src') or img.get('src')
                    if img_url and 'http' in img_url:
                        try:
                            self.ap.logger.info(f"处理第 {idx+1} 张图片，URL: {img_url}")
                            msg_chain.append(Image(url=img_url))
                            success_count += 1
                        except Exception as e:
                            self.ap.logger.error(f"处理第 {idx+1} 张图片失败：{str(e)}")
                
                # 发送所有图片
                if success_count > 0:
                    await ctx.reply(msg_chain)
                    await ctx.reply(MessageChain([f"处理完成，成功发送 {success_count} 张图片"]))
                else:
                    await ctx.reply(MessageChain(["未找到可用的图片"]))
                
            except Exception as e:
                self.ap.logger.error(f"处理失败：{str(e)}")
                await ctx.reply(MessageChain([f"处理失败：{str(e)}"]))
                return

    # 插件卸载时触发
    def __del__(self):
        pass
