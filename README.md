# CrownStar-AI-bot

CrownStar 是深度集成 DeepSeek 的企业级主权 AI 私有化平台，支持离线部署与国产化环境，确保数据不出域、模型自主可控，助力中国企业在合规框架下高效落地 AI。

## 软件架构

- 后端框架: Python / FastAPI
- AI 模型: DeepSeek 系列 (DeepSeek-V3, DeepSeek-R1)
- 部署方式: 私有化 (Kubernetes / Docker / 裸金属)
- 国产化适配: 昇腾 (Ascend) NPU、麒麟 (Kylin) OS、统信 (UOS)
- 安全体系: RBAC 权限控制、TDE 透明加密、离线运行

## 安装指南

1. 克隆仓库: git clone https://gitee.com/st3vensben/crown-star-ai-bot.git
2. 安装依赖: pip install -r requirements.txt (后续补充)
3. 配置环境变量: 复制 .env.example 并填写必要参数
4. 启动服务: python main.py

## 使用说明

- 管理员: 通过 Web 控制台管理模型、监控运行状态、配置权限
- 开发者: 调用 RESTful API 或 Python SDK 集成到业务系统
- 终端用户: 通过对话界面与 DeepSeek 智能体交互

## 贡献指南

本仓库为闭源企业版，暂不接受公开贡献。如需合作、定制或获取私有化部署支持，请联系: st3vens.ben@yandex.com

## 版权信息

Copyright © 2026 CrownStar. All rights reserved.
本软件为专有商业软件，未经书面授权不得复制、分发、反编译或用于任何商业用途。
