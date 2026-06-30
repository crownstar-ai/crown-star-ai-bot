# auto-email-system/app.py
# 完全无数据库的自动邮件系统
# 客户付款后自动发送 License Key，不存储任何客户信息

import os
import json
import hmac
import hashlib
import secrets
import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ===== 配置 =====
LICENSE_SECRET = os.environ.get('LICENSE_SECRET', 'change-me-now')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.yandex.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', SMTP_USER)

# 版本映射
TIER_MAP = {
    'basic': {'name': '基础版', 'price': '¥29,800', 'days_valid': 365},
    'pro': {'name': '专业版', 'price': '¥149,800', 'days_valid': 365},
    'enterprise': {'name': '企业版', 'price': '¥598,000', 'days_valid': 365},
}

# ===== 工具函数 =====
def generate_license(email, tier):
    """生成 License Key（不存储任何信息）"""
    raw = f"{email}|{tier}|{datetime.utcnow().isoformat()}|{secrets.token_hex(8)}"
    license_hash = hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
    # 格式化为易读形式
    formatted = '-'.join([license_hash[i:i+4] for i in range(0, 32, 4)])
    return formatted

def send_email(to, subject, html_content, text_content=None):
    """发送邮件"""
    msg = MIMEMultipart('alternative')
    msg['From'] = FROM_EMAIL
    msg['To'] = to
    msg['Subject'] = subject

    text_part = MIMEText(text_content or html_content, 'plain', 'utf-8')
    html_part = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(text_part)
    msg.attach(html_part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def build_license_email(email, tier, license_key):
    """构建 License 邮件内容"""
    tier_info = TIER_MAP.get(tier, {'name': tier, 'price': ''})
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 2rem; background: #f5f7fc; color: #1a1a2e;">
        <div style="background: white; border-radius: 1rem; padding: 2rem; box-shadow: 0 4px 24px rgba(0,0,0,0.04);">
            <h1 style="color: #0a2e5c; margin-top: 0;">👑 CrownStar</h1>
            <h2 style="color: #c9a84c;">感谢您的购买！</h2>
            <p>您已成功购买 <strong>{tier_info['name']}</strong>（{tier_info['price']}）。</p>
            <p>请妥善保管以下 License Key：</p>
            <div style="background: #e8ecf5; padding: 1rem; border-radius: 0.5rem; font-family: monospace; font-size: 1.2rem; text-align: center; letter-spacing: 0.05em; color: #0a2e5c;">
                {license_key}
            </div>
            <p style="margin-top: 1.5rem;">
                <a href="https://crownstar-ai.github.io/crown-star-ai-bot/website/download.html" 
                   style="background: #0a2e5c; color: white; padding: 0.6rem 1.5rem; border-radius: 2rem; text-decoration: none; font-weight: 600;">
                    📥 下载 CrownStar
                </a>
            </p>
            <p style="font-size: 0.85rem; color: #7a7a9a; margin-top: 1.5rem;">
                <strong>使用说明：</strong><br>
                1. 下载对应版本的安装包<br>
                2. 双击运行，首次启动时输入 License Key<br>
                3. 开始使用<br><br>
                <strong>注意事项：</strong><br>
                您的 License Key 已包含在邮件中，请勿丢失。<br>
                每个 License 仅限用于您购买的版本。
            </p>
            <hr style="border: 1px solid #e8ecf5; margin: 1.5rem 0;">
            <p style="font-size: 0.8rem; color: #aaa;">
                如有任何问题，请直接回复本邮件。<br>
                我们将在 8 小时内回复您。
            </p>
            <p style="font-size: 0.75rem; color: #ccc; text-align: center;">
                © 2026 CrownStar · 一次购买，终身免费升级
            </p>
        </div>
    </body>
    </html>
    """
    
    text = f"""
    CrownStar {tier_info['name']} License Key
    ========================================
    感谢您的购买！

    License Key：{license_key}

    下载地址：
    https://crownstar-ai.github.io/crown-star-ai-bot/website/download.html

    如遇任何问题，请直接回复本邮件。

    CrownStar 团队
    """
    return html, text

# ===== 核心：接收 Stripe Webhook =====
@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    # 1. 验证来源（生产环境必开）
    # payload = request.data
    # sig_header = request.headers.get('Stripe-Signature')
    # try:
    #     event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    # except:
    #     return jsonify({'error': 'Invalid signature'}), 400

    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400

    event_type = data.get('type')
    if event_type != 'checkout.session.completed':
        return jsonify({'status': 'ignored'}), 200

    session = data.get('data', {}).get('object', {})
    customer_email = session.get('customer_details', {}).get('email')
    if not customer_email:
        return jsonify({'error': 'No email'}), 400

    # 从 metadata 获取 tier，或从 product 名称推断
    tier = session.get('metadata', {}).get('tier', 'basic')
    if not tier or tier not in TIER_MAP:
        # 简单推断：从 product 名称中提取
        product_name = session.get('lines', {}).get('data', [{}])[0].get('description', '').lower()
        if '基础' in product_name or 'basic' in product_name:
            tier = 'basic'
        elif '专业' in product_name or 'pro' in product_name:
            tier = 'pro'
        elif '企业' in product_name or 'enterprise' in product_name:
            tier = 'enterprise'
        else:
            tier = 'basic'

    # 2. 生成 License（不存储任何信息）
    license_key = generate_license(customer_email, tier)

    # 3. 发送邮件
    html, text = build_license_email(customer_email, tier, license_key)
    success = send_email(customer_email, f'您的 CrownStar {TIER_MAP[tier]["name"]} License Key', html, text)

    if not success:
        return jsonify({'error': 'Email send failed'}), 500

    # 4. 记录订单到 CSV（轻量，不存储客户隐私，只存邮箱+密钥用于追溯）
    #    但你说“不保留客户数据”，所以这里也不存任何东西。唯一留存的是邮件，保存在客户邮箱中。
    #    如果你仍想简单记录（只记录时间+版本，不记邮箱），可以取消注释：
    # with open('orders.log', 'a') as f:
    #     f.write(f"{datetime.utcnow().isoformat()}|{tier}\n")

    return jsonify({'status': 'ok'}), 200

# ===== 健康检查 =====
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'CrownStar Auto-Email'})

# ===== 可选：客户自助查询 License（不存储数据，无法恢复） =====
# 因为不存储，所以无法提供查询页面。

# ===== 可选：投诉/退款入口（客户手动发邮件） =====
@app.route('/contact')
def contact_page():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>CrownStar 联系客服</title></head>
    <body style="font-family: system-ui; max-width: 600px; margin: 2rem auto; padding: 0 1rem;">
        <h1 style="color: #0a2e5c;">👑 CrownStar 客服</h1>
        <p>如您遇到任何问题（License 失效、下载问题、退款需求等），请直接发送邮件至：</p>
        <p style="font-size: 1.2rem;"><strong>st3vens.ben@yandex.com</strong></p>
        <p>我们将在 8 小时内回复您。</p>
        <hr style="margin: 2rem 0;">
        <p style="color: #7a7a9a; font-size: 0.85rem;">您也可以直接回复您收到的 License 邮件。</p>
    </body>
    </html>
    """)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
