import asyncio
from .main import WechatImageDownloader
from .mock_host import APIHost
from pkg.platform.types import PersonNormalMessageReceived, MessageChain, Image
from pkg.plugin.context import EventContext

class MockEventContext(EventContext):
    def __init__(self):
        super().__init__()
        self._return_values = []
    
    async def reply(self, message_chain):
        print(f"发送消息: {message_chain}")
        return True
    
    def add_return(self, key, value):
        print(f"添加返回值: {key} = {value}")
        self._return_values.append((key, value))
    
    def prevent_default(self):
        print("阻止默认行为")

async def main():
    # 创建 APIHost 实例
    host = APIHost()
    
    # 创建插件实例
    plugin = WechatImageDownloader(host)
    
    # 初始化插件
    await plugin.initialize()
    
    # 模拟消息事件
    test_url = "https://mp.weixin.qq.com/s/your_article_url"  # 替换为实际的微信文章URL
    test_message = f"/img {test_url}"
    
    # 创建模拟的事件上下文
    ctx = MockEventContext()
    ctx.event = PersonNormalMessageReceived()
    ctx.event.text_message = test_message
    
    # 调用插件处理函数
    await plugin.person_normal_message_received(ctx)

if __name__ == "__main__":
    asyncio.run(main()) 