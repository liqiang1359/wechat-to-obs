# WechatToObs 部署指南

## 推荐：Cloudflare Tunnel（无需改网络 / 无需 Certbot）

适合你的场景：**不用改路由器端口映射、不用开放 80/443、不用在服务器上申请证书**。  
微信 Webhook URL：`https://wechat.nobbn.com/wechat`

**完整分步说明见 → [`cloudflare-tunnel.md`](cloudflare-tunnel.md)**（含控制台设置、config.yml 详解、systemd、联调、排错）

### 快速步骤

```bash
# 1. 安装
sudo apt install cloudflared -y

# 2. 登录 + 创建隧道
cloudflared tunnel login
cloudflared tunnel create wechat-obs

# 3. DNS
cloudflared tunnel route dns wechat-obs wechat.nobbn.com

# 4. 配置 /etc/cloudflared/config.yml（见 cloudflared-config.yml）

# 5. 启动
sudo systemctl enable --now wechat-obs cloudflared

# 6. 验证
curl https://wechat.nobbn.com/health
```

---

## 备选：Cloudflare DNS 橙云代理 + 本机 Nginx

若服务器**已有公网 IP 且 80/443 已可达**，也可只用 Cloudflare 的 **DNS 代理（小橙云）** 做 HTTPS，不必自建证书：

1. Cloudflare DNS 添加 `A` 记录 `nobbn.com` → 服务器 IP，**开启代理（橙云）**
2. SSL/TLS 模式选 **灵活**（Cloudflare↔用户 HTTPS，Cloudflare↔源站 HTTP）或 **完全**（源站也需证书）
3. 本机 Nginx 监听 80，反代到 `127.0.0.1:5000`（见 [`nginx-wechat.conf`](nginx-wechat.conf)）
4. 微信 URL：`https://nobbn.com/wechat`

此方式仍需服务器能被公网访问，**不如 Tunnel 省心**。

---

## 备选：Let's Encrypt + Nginx（无 Cloudflare）

前提：`nobbn.com` DNS 直连服务器 IP。

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d nobbn.com -d www.nobbn.com
sudo certbot renew --dry-run
```

Nginx 配置见 [`nginx-wechat.conf`](nginx-wechat.conf)，微信 URL：`https://nobbn.com/wechat`

---

## 一、注册微信订阅号（前置）

1. 打开 https://mp.weixin.qq.com → **立即注册** → 选择 **订阅号**
2. 使用未注册过公众号的邮箱完成验证
3. 主体类型选 **个人**，完成身份证实名认证
4. 进入后台 **设置与开发 → 基本配置**，记录：
   - `AppID`
   - `AppSecret`（需管理员扫码查看）
5. 自定义 `Token` 字符串，填入 `config.yaml` 的 `wechat.token`
6. 公网 HTTPS 就绪后，配置服务器 URL（见上文 Cloudflare 或备选方案）

---

## Linux 部署 WechatToObs 服务

```bash
# 上传代码到服务器
scp -r wechat-to-obs/ user@your-server:/opt/wechat-to-obs

cd /opt/wechat-to-obs
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
chmod 600 config.yaml
# 编辑 config.yaml 填入微信凭证与 WebDAV 账号

sudo cp deploy/wechat-obs.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wechat-obs
sudo systemctl start wechat-obs
sudo systemctl status wechat-obs
```

Flask 只监听本机 `127.0.0.1:5000` 即可，由 Cloudflare Tunnel 或 Nginx 对外暴露。

---

## Windows 本地开发 + ngrok / Cloudflare Tunnel 联调

```powershell
cd wechat-to-obs
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml
python app.py
```

**ngrok**（临时）：

```bash
ngrok http 5000
# 微信 URL: https://xxxx.ngrok.io/wechat
```

**Cloudflare Tunnel**（与生产一致）：

```bash
cloudflared tunnel --url http://127.0.0.1:5000
# 会给出临时 https://xxx.trycloudflare.com，填入微信后台测试
```

---

## 使用方式

1. 微信中关注你的订阅号
2. 将文字、链接、图片、文件或聊天记录 **转发** 给订阅号
3. 内容自动经 WebDAV 同步到 Obsidian Vault 的 `Inbox/` 和 `Attachments/`

---

## WebDAV（dav.nobbn.com）说明

微信 Webhook 走 Cloudflare Tunnel；**Obsidian 同步的 WebDAV 可继续用你现有的 `dav.nobbn.com`**，两者互不影响。  
若 WebDAV 服务器也在内网、外网访问不了，同样可以为 `dav.nobbn.com` 再建一条 Cloudflare Tunnel 指向 WebDAV 服务。
