# eventsourcing/projections/projections.py – Read model projections
from ..store.event_store import get_event_store
from ..aggregates.conversation_aggregate import ConversationAggregate, ConfigurationAggregate

class ConversationProjection:
    def __init__(self):
        self.store = get_event_store()
    
    def get_conversation(self, conv_id: str):
        events = self.store.load_events(conv_id)
        if not events:
            return None
        agg = ConversationAggregate(conv_id)
        agg.load_from_events(events)
        return agg.to_dict()
    
    def get_config(self):
        events = self.store.load_events("global_config")
        agg = ConfigurationAggregate("global_config")
        if events:
            agg.load_from_events(events)
        return agg.to_dict()

_proj = None
def get_projection():
    global _proj
    if _proj is None:
        _proj = ConversationProjection()
    return _proj
