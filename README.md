# 👑 CrownStar – 企业级主权AI私有化平台

> 数据主权 · 自主可控 · 信创合规 · 开箱即用

CrownStar 是深度集成 DeepSeek 的企业级主权AI私有化平台，支持离线部署与国产化环境，确保数据不出域、模型自主可控，助力中国企业在合规框架下高效落地AI。

---

## 🎯 为什么选择 CrownStar？

| 维度 | CrownStar 优势 |
|------|----------------|
| **数据主权** | 100%私有化部署，数据不出企业网络 |
| **国产AI生态** | 深度集成DeepSeek，踩在中国最大AI生态上 |
| **信创合规** | 适配华为昇腾NPU / 麒麟OS / 统信UOS |
| **开箱即用** | 5分钟完成部署，无需复杂配置 |
| **企业级就绪** | JWT认证 + RBAC权限 + 审计日志 + 限流 |

---

## 📦 产品版本与价格

| 版本 | 适用客户 | 核心能力 | 价格 |
|------|----------|----------|------|
| 🆓 **社区评估版** | 开发者、技术验证 | DeepSeek集成 · 单机 · SQLite · 基础文档 | **免费下载** |
| 💼 **基础版** | 中小企业 | PostgreSQL · 用户管理 · 5×8支持 | ¥9,800/年 |
| 🏢 **专业版** | 中型企业 | RBAC · 审计日志 · 7×12支持 | ¥49,800/年 |
| 🏛️ **企业版** | 大型企业/政府 | 高可用 · 多租户 · 信创适配 · SLA | ¥198,000/年 |

> 💡 **所有版本均为固定年费，无按量付费，成本清晰可控。**
> 📌 **政府/央企客户可申请专项扶持价格。**

---

## 💳 如何购买付费版本

我们支持支付宝支付，方便客户快速完成购买：

### 支付宝（唯一支付方式）

扫码支付后，将支付截图发送至邮箱，我们将在 **30 分钟内** 发送企业版下载链接和授权码。

| 支付方式 | 操作 |
|----------|------|
| **支付宝** | 扫码支付 → 截图 → 发送至 st3vens.ben@yandex.com |

---

## 📧 购买流程

1. 选择版本（基础版 / 专业版 / 企业版）
2. 打开支付宝 APP，扫描下方二维码
3. 输入对应金额，完成支付
4. 保存支付截图
5. 将截图发送至：st3vens.ben@yandex.com
6. 30 分钟内收到 License Key 和下载链接
## 🚀 快速开始（5分钟部署）

### Docker方式（推荐）
\`\`\`bash
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-... crownstar/crownstar:latest
\`\`\`

### 源码部署
\`\`\`bash
git clone https://gitee.com/st3vensben/crown-star-ai-bot.git
cd crown-star-ai-bot
install.bat
# 编辑.env填入DEEPSEEK_API_KEY
uvicorn app.main:app --host 0.0.0.0 --port 8000
\`\`\`

---

## 📊 适用场景

| 行业 | 典型需求 | CrownStar 价值 |
|------|----------|----------------|
| 🏛️ **政府/央企** | 数据安全、信创合规 | 离线部署 + 国产化适配 |
| 🏦 **金融/保险** | 隐私保护、审计追溯 | 数据不出域 + 全链路审计 |
| 🏥 **医疗** | 患者数据保护 | 本地化部署 + 合规保障 |
| 🏭 **制造** | 核心工艺数据保护 | 边缘推理 + 数据不出厂 |
| 🎓 **教育/科研** | AI能力快速落地 | 开箱即用 + 低成本 |

---

## 🔒 安全与合规

✅ 私有化部署，数据不出域  
✅ 满足《数据安全法》《网络安全法》《个人信息保护法》  
✅ 信创（信息技术应用创新）认证  
✅ 华为昇腾NPU / 麒麟OS / 统信UOS 适配  
✅ 全链路审计追溯  

---

## 🤝 客户案例（示例）

### 某省级政务云
- **问题**：公文处理效率低，数据安全要求高
- **方案**：CrownStar 私有化部署 + AI辅助公文处理
- **效果**：效率提升60%

### 某国有大型银行
- **问题**：客服系统响应慢，数据不能出金融内网
- **方案**：CrownStar 智能客服系统
- **效果**：客服响应时间减少70%

### 某头部制造企业
- **问题**：质检系统准确率不足
- **方案**：CrownStar AI赋能质检
- **效果**：缺陷识别准确率提升35%

---


## 🧠 Premier R&D Projects

CrownStar is more than a product – it is a living R&D engine with two strategic Premier Projects:

1. **[CrownStar Neural Core](docs/premier-projects.md)** – The mathematical foundation already working in production.
2. **[Egg Apex vLLM](docs/premier-projects.md)** – A training‑free, sovereign language engine in development.

These projects accrue value to clients over time – automatic capability upgrades, increasing independence, and growing investment value.

📄 [Read the full Premier Projects overview](docs/premier-projects.md)
## 📞 联系我们

| 事项 | 联系方式 |
|------|----------|
| 商务合作 / 购买咨询 | st3vens.ben@yandex.com |
| 技术支持 | st3vens.ben@yandex.com |
| 渠道代理 | st3vens.ben@yandex.com |

**响应时间**：工作日 8 小时内回复

---

## 📄 许可证

CrownStar 是专有商业软件。社区评估版仅供评估测试使用，商业使用需购买授权。

未经 CrownStar 书面授权，不得复制、分发、反编译或用于任何商业用途。

---

**© 2026 CrownStar. All rights reserved.**

---

**立即体验**：https://gitee.com/st3vensben/crown-star-ai-bot/releases/tag/v1.0.0

