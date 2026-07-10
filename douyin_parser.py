#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音视频解析器。

旧版依赖 `https://dy.kukutool.com/api/parse` 的 v2 明文协议，
该协议现在已经被服务端停用，返回 `parse_v2_disabled`。
这里改为跟随站点当前使用的 v3 协议：先获取 auth，再用 AES-GCM
加密请求体提交到 parse 接口，最后解密响应数据。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from typing import Any

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.padding import PKCS7


STANDARD_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_B64 = "ZYXABCDEFGHIJKLMNOPQRSTUVWzyxabcdefghijklmnopqrstuvw9876543210-_"
XOR_KEY = 90
RESPONSE_AES_SECRET = "12345678901234567890123456789013"

BASE_URL = "https://dy.kukutool.com"
AUTH_ROUTE = "/api/auth-9e25f1"
PARSE_ROUTE = "/api/parse"
REQUEST_VERSION = 3
REQUEST_PROTOCOL_VERSION = 1

ACTIVE_PROFILE = {
    "auth_key_field": "k_9e25f1",
    "auth_seed_field": "s_9e25f1",
    "parse_key_field": "k_9e25f1",
    "parse_payload_field": "p_9e25f1",
    "parse_iv_field": "i_9e25f1",
    "parse_version_field": "r_9e25f1",
}

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
}


class DouyinParseError(Exception):
    """解析失败。"""


def xor_string(value: str, key: int = XOR_KEY) -> str:
    return "".join(chr(ord(char) ^ key) for char in value)


def block_reverse(value: str, block_size: int = 8) -> str:
    return "".join(value[i : i + block_size][::-1] for i in range(0, len(value), block_size))


def base64_custom_decode(value: str) -> str:
    decoded_chars = []
    for char in value:
        index = CUSTOM_B64.find(char)
        decoded_chars.append(STANDARD_B64[index] if index != -1 else char)
    return "".join(decoded_chars)


def decrypt_response_payload(data: str, iv: str) -> dict[str, Any]:
    data = xor_string(data)
    iv = xor_string(iv)
    data = block_reverse(data)
    iv = block_reverse(iv)
    data = base64_custom_decode(data)
    iv = base64_custom_decode(iv)

    encrypted_bytes = base64.b64decode(data)
    iv_bytes = base64.b64decode(iv)
    response_key = hashlib.sha256(RESPONSE_AES_SECRET.encode("utf-8")).digest()
    cipher = Cipher(algorithms.AES(response_key), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted_bytes) + decryptor.finalize()

    unpadder = PKCS7(128).unpadder()
    plain = unpadder.update(padded) + unpadder.finalize()
    return json.loads(plain.decode("utf-8"))


def derive_request_key(auth_key: str, auth_seed: str) -> bytes:
    return hashlib.sha256(f"{auth_key}:{auth_seed}".encode("utf-8")).digest()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def extract_url(text: str) -> str | None:
    """从分享文本中提取第一个 URL。"""
    match = re.search(r"http[s]?://[^\s]+", text)
    return match.group(0) if match else None


def _normalize_result(data: dict[str, Any]) -> dict[str, Any]:
    videos = data.get("videos")
    if isinstance(videos, list):
        for video in videos:
            fullinfo = video.get("video_fullinfo")
            if isinstance(fullinfo, list):
                for item in fullinfo:
                    video_type = item.get("type")
                    if video_type == "������" or "�" in str(video_type):
                        item["type"] = "超高清"
    return data


def _fetch_auth_context(
    session: requests.Session,
    request_url: str,
    page_path: str,
    is_batch: bool = False,
) -> dict[str, Any]:
    response = session.post(
        f"{BASE_URL}{AUTH_ROUTE}",
        json={
            "requestURL": request_url,
            "pagePath": page_path,
            "mode": "batch" if is_batch else "single",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _build_encrypted_request(
    params: dict[str, Any],
    auth_context: dict[str, Any],
) -> dict[str, Any]:
    auth_key = auth_context[ACTIVE_PROFILE["auth_key_field"]]
    auth_seed = auth_context[ACTIVE_PROFILE["auth_seed_field"]]
    key = derive_request_key(auth_key, auth_seed)
    nonce = os.urandom(12)
    plaintext = json.dumps(params, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload = AESGCM(key).encrypt(nonce, plaintext, None)

    return {
        "version": REQUEST_VERSION,
        ACTIVE_PROFILE["parse_key_field"]: auth_key,
        ACTIVE_PROFILE["parse_payload_field"]: base64.b64encode(payload).decode("ascii"),
        ACTIVE_PROFILE["parse_iv_field"]: base64.b64encode(nonce).decode("ascii"),
        ACTIVE_PROFILE["parse_version_field"]: REQUEST_PROTOCOL_VERSION,
    }


def parse_video_url(
    request_url: str,
    captcha_key: str = "",
    captcha_input: str = "",
) -> dict[str, Any]:
    """
    解析抖音视频 URL 或分享文本。

    Args:
        request_url: 抖音视频 URL 或完整分享文本
        captcha_key: 验证码 key
        captcha_input: 验证码输入

    Returns:
        解析后的字典
    """
    extracted_url = extract_url(request_url) or request_url.strip()
    if not extracted_url:
        raise DouyinParseError("未找到有效的抖音链接")

    session = build_session()
    payload_params = {
        "requestURL": extracted_url,
        "captchaKey": captcha_key,
        "captchaInput": captcha_input,
        "totalSuccessCount": "0",
        "successCount": "0",
        "firstSuccessDate": "",
        "pagePath": "/",
        "uwx_id": "",
        "isMobile": "False",
        "geoipIp": "",
    }

    try:
        auth_context = _fetch_auth_context(
            session=session,
            request_url=extracted_url,
            page_path=payload_params["pagePath"],
        )
        request_body = _build_encrypted_request(payload_params, auth_context)
        response = session.post(
            f"{BASE_URL}{PARSE_ROUTE}",
            json=request_body,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
    except requests.exceptions.RequestException as exc:
        raise DouyinParseError(f"请求失败: {exc}") from exc
    except KeyError as exc:
        raise DouyinParseError(f"解析协议字段缺失: {exc}") from exc

    if result.get("status") != 0:
        reason = result.get("reason")
        message = result.get("message")
        detail = reason or message or f"status={result.get('status')}"
        raise DouyinParseError(f"解析失败: {detail}")

    data = result.get("data")
    if result.get("encrypt"):
        try:
            data = decrypt_response_payload(result["data"], result["iv"])
        except Exception as exc:  # noqa: BLE001
            raise DouyinParseError(f"响应解密失败: {exc}") from exc

    if not isinstance(data, dict):
        raise DouyinParseError("接口返回了无法识别的数据格式")

    return _normalize_result(data)


def main() -> None:
    text = (
        "2.00 eBT:/ 03/20 L@J.vF :2pm 复制打开抖音极速版，看看【七分情感（教学）的作品】"
        "如果你提前知道了这一生是这般模样，你还会来吗？说实..."
        " https://v.douyin.com/_PyIG6JuccQ/"
    )
    url = extract_url(text)
    print("=" * 50)
    print("抖音视频解析器 - Python版")
    print("=" * 50)
    print(f"\n正在解析 URL: {url}\n")

    try:
        result = parse_video_url(text)
        print("解析成功\n")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}")


if __name__ == "__main__":
    main()
