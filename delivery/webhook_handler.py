# delivery/webhook_handler.py
# 部署命令：python webhook_handler.py

import os
import json
import hashlib
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== 配置（用你的实际值替换）=====
LICENSE_SECRET = os.environ.get('LICENSE_SECRET', 'change-me-now')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', 'whsec_xxx')  # Stripe Dashboard 中获取
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.yandex.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'st3vens.ben@yandex.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'your-password')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'st3vens.ben@yandex.com')
# =================================

TIER_MAP = {
    'basic': {'name': '基础版', 'price': '¥29,800'},
    'pro': {'name': '专业版', 'price': '¥149,800'},
    'enterprise': {'name': '企业版', 'price': '¥598,000'}
}

# 存储 License 的简单 JSON 数据库
DB_FILE = 'licenses.json'
if not os.path.exists(DB_FILE):
    with open(DB_FILE, 'w') as f:
        json.dump({}, f)

def load_db():
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

def generate_license(email, tier):
    db = load_db()
    raw = f"{email}|{tier}|{datetime.utcnow().isoformat()}|{secrets.token_hex(8)}"
    license_key = hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
    formatted = '-'.join([license_key[i:i+4] for i in range(0, 32, 4)])

    expiry = (datetime.utcnow() + timedelta(days=365)).isoformat()
    db[license_key] = {
        'email': email,
        'tier': tier,
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': expiry,
        'is_active': True,
        'formatted': formatted
    }
    save_db(db)
    return formatted, license_key

def send_email(to, subject, html_content, text_content=None):
    msg = MIMEMultipart('alternative')
    msg['From'] = FROM_EMAIL
    msg['To'] = to
    msg['Subject'] = subject

    part1 = MIMEText(text_content or html_content, 'plain', 'utf-8')
    part2 = MIMEText(html_content, 'html', 'utf-8')
    msg.attach(part1)
    msg.attach(part2)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, to, msg.as_string())

def send_license_email(email, tier, license_key):
    tier_info = TIER_MAP.get(tier, {'name': tier, 'price': ''})
    subject = f"🎉 您的 CrownStar {tier_info['name']} License Key"
    html = f"""
    <html><body style="font-family: system-ui; max-width: 600px; margin: auto; padding: 2rem; background: #f5f7fc;">
        <h1 style="color: #0a2e5c;">👑 CrownStar</h1>
        <h2 style="color: #c9a84c;">感谢您的购买！</h2>
        <p>您已成功购买 <strong>{tier_info['name']}（{tier_info['price']}）</strong>。</p>
        <p><strong>您的 License Key：</strong></p>
        <div style="background: #e8ecf5; padding: 1rem; border-radius: 0.5rem; font-family: monospace; font-size: 1.1rem; text-align: center;">
            {license_key}
        </div>
        <p><br><a href="https://crownstar-ai.github.io/crown-star-ai-bot/website/download.html" style="background: #0a2e5c; color: white; padding: 0.6rem 1.5rem; border-radius: 2rem; text-decoration: none;">📥 下载软件</a></p>
        <p style="font-size: 0.85rem; color: #7a7a9a;">如需帮助，请联系 st3vens.ben@yandex.com</p>
        <hr style="border: 1px solid #e8ecf5;">
        <p style="font-size: 0.75rem; color: #aaa;">© 2026 CrownStar · 一次购买，终身免费升级</p>
    </body></html>
    """
    text = f"""
    CrownStar {tier_info['name']} License Key
    ========================================
    感谢您的购买！

    License Key：{license_key}

    下载地址：
    https://crownstar-ai.github.io/crown-star-ai-bot/website/download.html

    如有问题，请回复本邮件。
    """
    send_email(email, subject, html, text)

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    # 验证 Stripe 签名（生产环境必须启用）
    # payload = request.data
    # sig_header = request.headers.get('Stripe-Signature')
    # try:
    #     event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    # except:
    #     return jsonify({'error': 'Invalid signature'}), 400

    data = request.json
    event_type = data.get('type')
    if event_type == 'checkout.session.completed':
        session = data['data']['object']
        email = session['customer_details']['email']
        tier = session.get('metadata', {}).get('tier', 'basic')
        # 如果 metadata 没有 tier，可以通过 product name 判断
        if not tier:
            product_name = session['lines']['data'][0]['description'].lower()
            if '基础' in product_name: tier = 'basic'
            elif '专业' in product_name: tier = 'pro'
            elif '企业' in product_name: tier = 'enterprise'

        formatted, raw = generate_license(email, tier)
        send_license_email(email, tier, formatted)

        # 记录订单到 CSV
        import csv
        with open('orders.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.utcnow().isoformat(),
                email,
                tier,
                formatted,
                'sent'
            ])
        return jsonify({'status': 'ok'}), 200
    return jsonify({'status': 'ignored'}), 200

@app.route('/health')
def health():
    return jsonify({'status': 'delivery service running'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
