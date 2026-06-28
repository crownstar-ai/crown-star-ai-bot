# eventsourcing/commands/handlers.py – Command handlers
import uuid
from ..store.event_store import get_event_store
from ..aggregates.conversation_aggregate import ConversationAggregate, ConfigurationAggregate

class CommandHandler:
    def __init__(self):
        self.store = get_event_store()
    
    def handle_create_conversation(self, user_id: str, tier: str) -> str:
        agg_id = str(uuid.uuid4())
        conv = ConversationAggregate.create(agg_id, user_id, tier)
        self.store.append_events(agg_id, 0, conv.get_uncommitted_events())
        conv.mark_committed()
        return agg_id
    
    def handle_add_message(self, conv_id: str, user_msg: str, assistant_msg: str, modules: list, model: str, latency_ms: int) -> bool:
        events = self.store.load_events(conv_id)
        if not events:
            return False
        conv = ConversationAggregate(conv_id)
        conv.load_from_events(events)
        exp_version = conv.version
        conv.add_message(user_msg, assistant_msg, modules, model, latency_ms)
        ok = self.store.append_events(conv_id, exp_version, conv.get_uncommitted_events())
        if ok:
            conv.mark_committed()
        return ok
    
    def handle_toggle_module(self, module: str, enabled: bool):
        agg_id = "global_config"
        events = self.store.load_events(agg_id)
        cfg = ConfigurationAggregate(agg_id)
        if events:
            cfg.load_from_events(events)
        exp = cfg.version
        cfg.toggle_module(module, enabled)
        self.store.append_events(agg_id, exp, cfg.get_uncommitted_events())
        cfg.mark_committed()
    
    def handle_change_tier(self, new_tier: str):
        agg_id = "global_config"
        events = self.store.load_events(agg_id)
        cfg = ConfigurationAggregate(agg_id)
        if events:
            cfg.load_from_events(events)
        exp = cfg.version
        cfg.change_tier(new_tier)
        self.store.append_events(agg_id, exp, cfg.get_uncommitted_events())
        cfg.mark_committed()
    
    def handle_switch_model(self, new_model: str):
        agg_id = "global_config"
        events = self.store.load_events(agg_id)
        cfg = ConfigurationAggregate(agg_id)
        if events:
            cfg.load_from_events(events)
        exp = cfg.version
        cfg.switch_model(new_model)
        self.store.append_events(agg_id, exp, cfg.get_uncommitted_events())
        cfg.mark_committed()

_handler = None
def get_command_handler():
    global _handler
    if _handler is None:
        _handler = CommandHandler()
    return _handler
