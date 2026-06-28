# analytics/billing_engine.py – Pricing and billing logic
from typing import Dict, Optional
from datetime import datetime, timedelta
import json

class BillingEngine:
    # Tier pricing per million characters (input+output)
    TIER_PRICES = {
        'free_pay_per_use': 0.002,   # $0.002 per 1k chars = $2 per million
        'basic': 39.0,                # one-time
        'pro': 499.0,                 # one-time
        'enterprise': 39999.0,        # annual
    }
    
    # Overage rates per million characters beyond limits
    OVERAGE_RATES = {
        'free_pay_per_use': 0.002,
        'basic': 0.001,
        'pro': 0.0005,
        'enterprise': 0.0001
    }
    
    TIER_LIMITS = {
        'free_pay_per_use': {'input': 500000, 'output': 1000000},
        'basic': {'input': 2000000, 'output': 5000000},
        'pro': {'input': 5000000, 'output': 20000000},
        'enterprise': {'input': 100000000, 'output': 500000000}
    }
    
    @classmethod
    def calculate_request_cost(cls, tier: str, input_chars: int, output_chars: int) -> float:
        if tier == 'basic' or tier == 'pro' or tier == 'enterprise':
            # One-time tiers have no per-request cost (but may have overage)
            return 0.0
        total_chars = input_chars + output_chars
        cost = (total_chars / 1000) * cls.TIER_PRICES[tier]
        return round(cost, 6)
    
    @classmethod
    def calculate_monthly_usage_cost(cls, user_id: str, analytics_service) -> Dict:
        # Get total usage for past 30 days
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        summary = analytics_service.get_usage_summary(start.date().isoformat(), end.date().isoformat())
        cost = summary['total_cost']
        return {
            'period_start': start.isoformat(),
            'period_end': end.isoformat(),
            'total_cost': cost,
            'breakdown': summary
        }
    
    @classmethod
    def check_rate_limit(cls, tier: str, input_chars: int, output_chars: int) -> bool:
        limits = cls.TIER_LIMITS.get(tier, cls.TIER_LIMITS['free_pay_per_use'])
        return input_chars <= limits['input'] and output_chars <= limits['output']
    
    @classmethod
    def get_tier_price(cls, tier: str) -> float:
        return cls.TIER_PRICES.get(tier, 0.0)
