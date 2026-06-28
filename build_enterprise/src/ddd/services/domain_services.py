# ddd/services/domain_services.py – Domain services for cross‑aggregate logic
from typing import Optional, List
from ..value_object import Tier, Money, Percentage, UserId, ConversationId
from ..entities.domain_entities import User, Conversation, ModuleConfiguration
from ..repositories.repositories import UserRepository, ConversationRepository, ModuleConfigurationRepository

class PricingService:
    """Domain service for calculating costs based on tier and usage"""
    
    # Cost per thousand characters (USD)
    TIER_RATES = {
        "free_pay_per_use": 0.002,
        "basic": 0.001,
        "pro": 0.0005,
        "enterprise": 0.0001
    }
    
    def calculate_cost(self, tier: Tier, input_chars: int, output_chars: int) -> Money:
        rate = self.TIER_RATES.get(tier.name, 0.002)
        total_chars = input_chars + output_chars
        amount = (total_chars / 1000) * rate
        return Money(round(amount, 6))
    
    def apply_discount(self, cost: Money, discount_percentage: Percentage) -> Money:
        discounted = cost.amount * (1 - discount_percentage.value)
        return Money(round(discounted, 6), cost.currency)

class ConversationService:
    """Domain service for conversation operations"""
    
    def __init__(self, conversation_repo: ConversationRepository, user_repo: UserRepository, pricing: PricingService):
        self.conversation_repo = conversation_repo
        self.user_repo = user_repo
        self.pricing = pricing
    
    def add_message(self, conversation_id: ConversationId, user_id: UserId, user_message: str, assistant_message: str, modules_active: List[str], model: str, latency_ms: int) -> bool:
        conv = self.conversation_repo.find_by_id(conversation_id)
        if not conv or conv.user_id != user_id:
            return False
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return False
        # Calculate cost
        cost = self.pricing.calculate_cost(conv.tier, len(user_message), len(assistant_message))
        conv.add_message(user_message, assistant_message, modules_active, model, latency_ms)
        user.record_request(cost)
        self.conversation_repo.save(conv)
        self.user_repo.save(user)
        return True
    
    def get_user_conversations(self, user_id: UserId, limit: int = 20) -> List[Conversation]:
        return self.conversation_repo.find_by_user(user_id, limit)

class UserRegistrationService:
    """Domain service for user registration"""
    
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
    
    def register(self, username: str, email: str, initial_tier: Tier = None) -> User:
        if initial_tier is None:
            initial_tier = Tier.free()
        existing = self.user_repo.find_by_username(username)
        if existing:
            raise ValueError(f"Username {username} already exists")
        from ..value_object import UserId, ModelName
        user = User(
            id=UserId.generate(),
            username=username,
            email=email,
            tier=initial_tier,
            current_model=ModelName.deepseek_v2(),
            modules={}
        )
        self.user_repo.save(user)
        return user

class ModuleActivationService:
    """Domain service for module activation logic"""
    
    def __init__(self, config_repo: ModuleConfigurationRepository, user_repo: UserRepository):
        self.config_repo = config_repo
        self.user_repo = user_repo
    
    def toggle_global_module(self, module_name: str, enabled: bool) -> ModuleConfiguration:
        config = self.config_repo.get()
        config.toggle_module(module_name, enabled)
        self.config_repo.save(config)
        return config
    
    def toggle_user_module(self, user_id: UserId, module_name: str, enabled: bool) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        user.toggle_module(module_name, enabled)
        self.user_repo.save(user)
        return user
