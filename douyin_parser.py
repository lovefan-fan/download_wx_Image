#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音视频下载API解析器 - Python实现
传入requestURL则返回解析后的内容
"""

import hashlib
import json
import time
import random
import string
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64

# ============================
# 常量定义
# ============================
STANDARD_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_B64 = 'ZYXABCDEFGHIJKLMNOPQRSTUVWzyxabcdefghijklmnopqrstuvw9876543210-_'
XOR_KEY = 90
AES_KEY = b'12345678901234567890123456789013'
SECRET_KEY = '5Q0NvQxD0zdQ5RLQy5xs'
API_URL = 'https://dy.kukutool.com/api/parse'


# ============================
# 工具函数
# ============================

def replace_bd(s: str) -> str:
    """替换字符串中的 b 和 d"""
    return s.replace('b', '#').replace('d', 'b').replace('#', 'd')


def generate_signature(params: dict, salt: str, ts: int, secret: str) -> str:
    """生成签名"""
    sorted_keys = sorted(params.keys())
    query_string = '&'.join([f"{key}={params[key]}" for key in sorted_keys])
    sign_string = f"{query_string}&salt={salt}&ts={ts}&secret={secret}"
    md5_hash = hashlib.md5(sign_string.encode('utf-8')).hexdigest()
    return replace_bd(md5_hash)


def create_signed_params(params: dict, secret: str = SECRET_KEY) -> dict:
    """创建带签名的完整参数对象"""
    ts = int(time.time())
    salt = ''.join(random.choices(string.ascii_lowercase + string.digits, k=11))
    sign = generate_signature(params, salt, ts, secret)
    return {**params, 'ts': ts, 'salt': salt, 'sign': sign}


def xor_string(s: str, key: int = XOR_KEY) -> str:
    """XOR 字符串解密"""
    return ''.join([chr(ord(c) ^ key) for c in s])


def block_reverse(s: str, block_size: int = 8) -> str:
    """块反转"""
    result = []
    for i in range(0, len(s), block_size):
        block = s[i:i + block_size]
        result.append(block[::-1])
    return ''.join(result)


def base64_custom_decode(s: str) -> str:
    """自定义 Base64 解码"""
    result = []
    for char in s:
        if char in CUSTOM_B64:
            index = CUSTOM_B64.index(char)
            result.append(STANDARD_B64[index])
        else:
            result.append(char)
    return ''.join(result)


def aes_decrypt(encrypted_data: str, iv: str, key: bytes = AES_KEY) -> dict:
    """AES 解密"""
    encrypted_bytes = base64.b64decode(encrypted_data)
    iv_bytes = base64.b64decode(iv)
    cipher = AES.new(key, AES.MODE_CBC, iv_bytes)
    decrypted = cipher.decrypt(encrypted_bytes)
    decrypted = unpad(decrypted, AES.block_size)
    return json.loads(decrypted.decode('utf-8'))


def decrypt_response(data: str, iv: str) -> dict:
    """完整解密响应数据"""
    data = xor_string(data, XOR_KEY)
    iv = xor_string(iv, XOR_KEY)
    data = block_reverse(data)
    iv = block_reverse(iv)
    data = base64_custom_decode(data)
    iv = base64_custom_decode(iv)
    return aes_decrypt(data, iv, AES_KEY)


# ============================
# 主要功能函数
# ============================

def parse_video_url(request_url: str, 
                    captcha_key: str = '', 
                    captcha_input: str = '',
                    secret: str = SECRET_KEY) -> dict:
    """
    解析抖音视频URL或分享文本
    
    Args:
        request_url: 抖音视频URL或完整分享文本
        captcha_key: 验证码key（可选）
        captcha_input: 验证码输入（可选）
        secret: 签名密钥
    
    Returns:
        解析后的视频信息字典
    """
    params = {
        'requestURL': request_url,
        'captchaKey': captcha_key,
        'captchaInput': captcha_input
    }
    print(f"params={params}")
    signed_params = create_signed_params(params, secret)
    
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,en-GB;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://dy.kukutool.com',
        'Pragma': 'no-cache',
        'Referer': 'https://dy.kukutool.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
        'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    try:
        response = requests.post(
            API_URL,
            json=signed_params,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('status') != 0:
            raise Exception(f"API返回错误状态: {result.get('status')}")
        
        if result.get('encrypt'):
            return decrypt_response(result['data'], result['iv'])
        else:
            return result.get('data')
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"请求失败: {str(e)}")
    except Exception as e:
        raise Exception(f"解析失败: {str(e)}")
def extract_url(text):
    import re
    """
    从文本中提取URL链接
    
    参数:
        text (str): 包含URL的文本
        
    返回:
        str: 提取到的第一个URL，如果没有找到则返回None
    """
    # 匹配常见的URL模式
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    
    match = url_pattern.search(text)
    if match:
        return match.group()
    return None

# ============================
# 使用示例
# ============================

def main():
    """主函数 - 使用示例"""
    # 使用纯URL（更稳定）
    # test_url = 'https://v.douyin.com/MPXX7C9U-SU/'
    # test_url = '1.25 09/06 LWz:/X@m.dA 想创业的看过来!AI 结合实体店，条条视频都能火 # 实体经营 # Ai创业 # Ai # 实体店 # 实体店引流 https://v.douyin.com/MPXX7C9U-SU/复制此链接，打开Dou音搜索，直接观看视频!'
    text = '1.25 09/06 LWz:/X@m.dA 想创业的看过来!AI 结合实体店，条条视频都能火 # 实体经营 # Ai创业 # Ai # 实体店 # 实体店引流 https://v.douyin.com/MPXX7C9U-SU/复制此链接，打开Dou音搜索，直接观看视频!'
    test_url = extract_url(text)
    print("=" * 50)
    print("抖音视频解析器 - Python版")
    print("=" * 50)
    print(f"\n正在解析URL: {test_url}\n")
    
    try:
        result = parse_video_url(test_url)
        
        print("✅ 解析成功！\n")
        print("=" * 50)
        print("解析结果:")
        print("=" * 50)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 提取常用信息
        if 'title' in result:
            print(f"\n📹 视频标题: {result['title']}")
        if 'url' in result:
            print(f"🔗 视频链接: {result['url']}")
        if 'cover' in result:
            print(f"🖼️  封面: {result['cover']}")
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")


if __name__ == '__main__':
    main()
