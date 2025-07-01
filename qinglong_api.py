import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

class QingLongAPI:
    def __init__(self, qinglong_url: str, client_id: str, client_secret: str):
        self.qinglong_url = qinglong_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        self.timeout = (5, 10)

    def make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            kwargs['timeout'] = self.timeout
            if 'headers' not in kwargs:
                kwargs['headers'] = self.headers
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"请求失败 ({method} {url}): {str(e)}")
            return None

    def get_token(self):
        url = f"{self.qinglong_url}/open/auth/token"
        query = {
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        response = self.make_request("get", url, params=query)
        if response:
            return response.json().get("data", {}).get("token")
        return None

    def get_envs(self, name: str = 'xiaomi'):
        url = f"{self.qinglong_url}/open/envs"
        headers = {
            "Authorization": f"Bearer {self.get_token()}"
        }
        query = {
            "searchValue": name
        }
        response = self.make_request("get", url, headers=headers, params=query)
        if response:
            if response.json().get("data") != []:
                return response.json().get("data")
            else:
                self.create_env(name, "")
        return None

    def create_env(self, name: str, value: str):
        url = f"{self.qinglong_url}/open/envs"
        headers = {
            "Authorization": f"Bearer {self.get_token()}"
        }
        data = [{
            "name": name,
            "value": value
        }]
        response = self.make_request("post", url, headers=headers, json=data)
        if response:
            return response.json().get("data")
        return None

    def update_env(self, name: str, value: str):
        url = f"{self.qinglong_url}/open/envs"
        headers = {
            "Authorization": f"Bearer {self.get_token()}"
        }
        query = {
            "searchValue": name
        }
        response = self.make_request("get", url, headers=headers, params=query)
        if response:
            data_list = response.json().get("data")
            if not data_list:
                # 不存在则自动添加
                return self.create_env(name, value)
            else:
                old_value = data_list[0].get("value")
                new_value = list(old_value)
                new_value.append(value)
                data = {
                    "id": data_list[0].get("id"),
                    "name": name,
                    "value": new_value
                }
                response = self.make_request("put", url, headers=headers, json=data)
                if response:
                    return response.json().get("data")
        return None 