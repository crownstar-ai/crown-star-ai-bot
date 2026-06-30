# delivery/manual_send.py
# 手动发送 License Key 给客户（不使用 Webhook）
# 用法：python manual_send.py customer@example.com basic

import sys
import csv
from datetime import datetime
from webhook_handler import generate_license, send_license_email

if len(sys.argv) < 3:
    print("用法: python manual_send.py <email> <tier>")
    print("  tier: basic / pro / enterprise")
    sys.exit(1)

email = sys.argv[1]
tier = sys.argv[2]

formatted, raw = generate_license(email, tier)
send_license_email(email, tier, formatted)

# 记录订单
with open('orders.csv', 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        datetime.utcnow().isoformat(),
        email,
        tier,
        formatted,
        'sent'
    ])

print(f"✅ License 已发送到 {email}")
print(f"🔑 Key: {formatted}")
