cd D:\CrownStar-Absolute\crown-star-ai-bot\crown-star-ai-bot

# 备份当前 README
Copy-Item README.md README.md.backup2

# 新的 README 内容（简化版，保留核心销售信息）
$newReadme = @"
# 👑 CrownStar – 企业级主权AI私有化平台

> 数据主权 · 自主可控 · 信创合规 · 开箱即用

CrownStar 是深度集成 **DeepSeek** 的企业级主权AI私有化平台。它让您的企业**完全拥有自己的AI基础设施**——数据不出域，模型自主可控，5分钟即可完成部署。

---

## 🎯 为什么选择 CrownStar？

| 维度 | CrownStar 优势 |
|------|----------------|
| 🔒 **数据主权** | 100%私有化部署，数据永不离开您的网络 |
| 🇨🇳 **国产AI生态** | 深度集成 DeepSeek，踩在中国最大AI生态上 |
| 🛡️ **信创合规** | 适配华为昇腾NPU / 麒麟OS / 统信UOS |
| ⚡ **开箱即用** | 5分钟完成部署，无需复杂配置 |
| 🔄 **终身免费升级** | 一次购买，永久享受所有未来版本 |

---

## 💰 定价方案（一次性买断 · 终身授权）

| 版本 | 价格 | 立即购买 |
|------|------|----------|
| 🆓 社区评估版 | **免费** | [下载](https://gitee.com/st3vensben/crown-star-ai-bot/releases/tag/v1.0.0) |
| 💼 基础版 | **¥29,800** | [购买](docs/buy/BUY_BASIC.md) |
| 🏢 专业版 | **¥149,800** | [购买](docs/buy/BUY_PRO.md) |
| 🏛️ 企业版 | **¥598,000** | [购买](docs/buy/BUY_ENTERPRISE.md) |
| 🔐 源码授权版 | **面议** | [咨询](docs/buy/BUY_SOURCE.md) |

> 💡 **一次购买，终身免费升级。** 所有付费版本包含永久免费更新。

---

## 🛒 购买流程（3步搞定）

| 步骤 | 操作 |
|------|------|
| 1️⃣ | **选择版本** – 点击上方的“购买”链接 |
| 2️⃣ | **支付宝扫码付款** – 按照页面指引完成支付 |
| 3️⃣ | **获取 License Key** – 30 分钟内邮件收到授权码 |

📧 **支付后发送截图至**：st3vens.ben@yandex.com

---

## 🚀 快速开始（5分钟部署）

### Docker方式（推荐）
\`\`\`bash
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-... crownstar/crownstar:latest
\`\`\`

### 源码部署
\`\`\`bash
git clone https://gitee.com/st3vensben/crown-star-ai-bot.git
cd crown-star-ai-bot
.\install.bat
# 编辑 .env 填入 DEEPSEEK_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
\`\`\`

---

## 📊 适用行业

| 行业 | 典型需求 | CrownStar 价值 |
|------|----------|----------------|
| 🏛️ **政府/央企** | 数据安全、信创合规 | 离线部署 + 国产化适配 |
| 🏦 **金融/保险** | 隐私保护、审计追溯 | 数据不出域 + 全链路审计 |
| 🏥 **医疗** | 患者数据保护 | 本地化部署 + 合规保障 |
| 🏭 **制造** | 核心工艺数据保护 | 边缘推理 + 数据不出厂 |

---

## 🔒 安全与合规

✅ 私有化部署，数据不出域  
✅ 满足《数据安全法》《网络安全法》《个人信息保护法》  
✅ 信创（信息技术应用创新）认证  
✅ 华为昇腾NPU / 麒麟OS / 统信UOS 适配  
✅ 全链路审计追溯  

---

## 🧠 Premier R&D Projects

CrownStar 是一个活着的研发引擎。您的购买包含所有未来更新：

1. **[CrownStar Neural Core](docs/premier-projects.md)** – 数学基础（已在生产中工作）
2. **[Egg Apex vLLM](docs/premier-projects.md)** – 无需训练的语言引擎（开发中）

📄 [阅读完整的 Premier Projects 概述](docs/premier-projects.md)

---

## 📞 联系我们

| 事项 | 联系方式 |
|------|----------|
| 商务合作 / 购买咨询 | st3vens.ben@yandex.com |
| 技术支持 | st3vens.ben@yandex.com |

**响应时间**：工作日 8 小时内回复

---

## 📄 许可证

CrownStar 是专有商业软件。社区评估版仅供评估测试使用，商业使用需购买授权。

---

**© 2026 CrownStar. All rights reserved.**

**立即体验免费版**：https://gitee.com/st3vensben/crown-star-ai-bot/releases/tag/v1.0.0
"@

$newReadme | Set-Content -Path README.md -Encoding UTF8

# 提交并推送
git add README.md
git commit -m "🎯 更新 README：新定价表、购买链接、Premier Projects"
git push origin master

Write-Host "✅ README.md 已更新并推送！" -ForegroundColor Green
Write-Host "🔗 https://gitee.com/st3vensben/crown-star-ai-bot" -ForegroundColor Cyan