import requests
import time
import json
from typing import Optional, List, Dict
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random

class EmailForwarder:
    def __init__(self):
        self.temp_mail_api = "https://tempmail.plus/api"
        self.wechat_api = "http://fan.jiuchengyixi.top:3000/push/root"
        self.wechat_token = "812858338"
        self.wechat_channel = "test"
        self.email_address = "aafob@mailto.plus"  # 临时邮箱地址
        self.last_mail_id = None  # 用于记录最后处理的邮件ID
        
        # 配置请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://tempmail.plus/",
            "Origin": "https://tempmail.plus",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        
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
        """
        统一的请求处理方法，包含重试和超时机制
        """
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
            print(f"请求失败 ({method} {url}): {str(e)}")
            return None

    def delete_email(self, mail_id: int) -> bool:
        """
        删除指定ID的邮件
        """
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
            print(f"删除邮件时出错: {str(e)}")
            return False

    def get_email_content(self, mail_id: int) -> Optional[Dict]:
        """
        获取邮件详细内容
        """
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
                    print(f"获取邮件内容失败: {mail_id}")
                    return None
                return data
            return None
            
        except Exception as e:
            print(f"获取邮件内容时出错: {str(e)}")
            return None

    def get_email(self) -> Optional[List[Dict]]:
        """
        从tempmail.plus获取邮件列表
        返回新邮件列表
        """
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
                    print("获取邮件列表失败")
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
            print(f"获取邮件时出错: {str(e)}")
            return None

    def forward_to_wechat(self, title: str, description: str) -> bool:
        """
        转发消息到微信
        """
        try:
            data = {
                "title": title,
                "description": description,
                "token": self.wechat_token,
                "channel": self.wechat_channel
            }
            # 微信接口不需要tempmail的请求头
            response = self.make_request("POST", self.wechat_api, json=data, headers={})
            return response is not None and response.status_code == 200
        except Exception as e:
            print(f"转发到微信时出错: {str(e)}")
            return False

    def run(self):
        """
        主运行循环
        """
        print(f"开始监控邮箱: {self.email_address}")
        consecutive_errors = 0  # 连续错误计数
        
        while True:
            try:
                new_mails = self.get_email()
                if new_mails:
                    consecutive_errors = 0  # 重置错误计数
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
                            
                            success = self.forward_to_wechat("邮件转发", mail_info)
                            if success:
                                print(f"消息转发成功: {mail_id}")
                                # 转发成功后删除邮件
                                if self.delete_email(mail_id):
                                    print(f"邮件删除成功: {mail_id}")
                                else:
                                    print(f"邮件删除失败: {mail_id}")
                            else:
                                print(f"消息转发失败: {mail_id}")
                else:
                    consecutive_errors = 0  # 重置错误计数
                    
            except Exception as e:
                consecutive_errors += 1
                print(f"运行时出错: {str(e)}")
                if consecutive_errors >= 3:  # 如果连续出错3次
                    print("连续出错，等待较长时间后重试...")
                    time.sleep(300)  # 等待5分钟
                    consecutive_errors = 0  # 重置错误计数
                    continue
            
            # 添加随机延迟，避免固定间隔
            delay = 10 + random.uniform(-2, 2)  # 8-12秒的随机延迟
            time.sleep(delay)

if __name__ == "__main__":
    forwarder = EmailForwarder()
    forwarder.run() 