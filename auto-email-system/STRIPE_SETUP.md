# auto-email-system/STRIPE_SETUP.md
# Stripe Webhook 配置步骤

1. 登录 Stripe Dashboard
2. 进入 Developers → Webhooks
3. 点击 "Add endpoint"
4. Endpoint URL: https://你的域名.com/webhook/stripe
5. 选择事件: checkout.session.completed
6. 获取 Signing secret (whsec_xxx)
7. 填入 .env 文件中的 STRIPE_WEBHOOK_SECRET

本地测试:
- 使用 Stripe CLI: stripe listen --forward-to localhost:8080/webhook/stripe
- 然后触发测试支付
