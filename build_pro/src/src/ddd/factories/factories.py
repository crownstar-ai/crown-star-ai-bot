# ddd/factories/factories.py – Domain object factories
from typing import Optional, List
from ..value_object import UserId, ConversationId, Tier, ModelName, Money
from ..entities.domain_entities import User, Conversation, ModuleConfiguration

class UserFactory:
    @staticmethod
    def create(username: str, email: str, tier: Tier = None, model: ModelName = None) -> User:
        if tier is None:
            tier = Tier.free()
        if model is None:
            model = ModelName.deepseek_v2()
        return User(
            id=UserId.generate(),
            username=username,
            email=email,
            tier=tier,
            current_model=model,
            modules={}
        )

class ConversationFactory:
    @staticmethod
    def create(user_id: UserId, tier: Tier = None) -> Conversation:
        if tier is None:
            tier = Tier.free()
        return Conversation(
            id=ConversationId.generate(),
            user_id=user_id,
            tier=tier,
            messages=[]
        )
    
    @staticmethod
    def from_existing(user_id: UserId, messages: List[dict]) -> Conversation:
        conv = ConversationFactory.create(user_id)
        conv.messages = messages
        conv.version = len(messages) + 1
        return conv

class ModuleConfigurationFactory:
    @staticmethod
    def create_default() -> ModuleConfiguration:
        config = ModuleConfiguration()
        # Default module states (all disabled)
        default_modules = [
            "base_3layer_jacobian", "hessian_backprop", "universal_approx",
            "gurney_3stage", "yegnanarayana_tensor", "haykin_recursive",
            "bishop_probabilistic", "zurada_indexed", "ultra_super_model"
        ]
        for mod in default_modules:
            config.modules[mod] = False
        return config
