# 微信文章图片下载插件

这是一个用于下载微信文章图片的插件。通过简单的命令，你可以快速下载微信文章中的所有图片。

## 功能特点

- 支持通过 `/img` 命令下载微信文章中的图片
- 自动保存图片到本地 `wechat_images` 文件夹
- 支持个人消息和群消息
- 下载过程中显示进度提示
- 自动发送下载的图片
- 支持处理 `data-src` 和 `src` 属性的图片链接

## 使用方法

1. 在聊天中发送以下格式的消息：
```
/img 微信文章链接
```

例如：
```
/img https://mp.weixin.qq.com/s/xxx
```

2. 插件会自动：
   - 解析文章中的图片
   - 下载所有图片
   - 将图片保存到 `wechat_images` 文件夹
   - 发送下载成功的提示
   - 自动发送下载的图片

## 配置说明

插件支持以下配置项：

- `user_agent`: HTTP 请求的用户代理字符串
  - 默认值：`Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36`
  - 可选配置，建议保持默认值

## 注意事项

1. 确保有足够的磁盘空间存储下载的图片
2. 图片会以 `image_0.jpg`、`image_1.jpg` 等格式保存
3. 如果下载失败，会显示具体的错误信息
4. 建议在下载大量图片时注意网络状况

## 依赖要求

- Python 3.6+
- requests
- beautifulsoup4

## 安装依赖

```bash
pip install requests beautifulsoup4
```
