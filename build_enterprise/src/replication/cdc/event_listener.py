# replication/cdc/event_listener.py – Listen to change events from Kafka
import json
import threading
import time
from kafka import KafkaConsumer
from typing import Callable, Dict, List, Optional
import logging

logger = logging.getLogger("crownstar.cdc")

class CDCEventListener:
    def __init__(self, bootstrap_servers: str = "localhost:9092", group_id: str = "crownstar-cdc"):
        self.bootstrap_servers = bootstrap_servers
        self.group_id = group_id
        self.consumers = {}
        self.callbacks = {}
        self.running = False
        self.threads = []
    
    def subscribe(self, topic_pattern: str, callback: Callable[[Dict], None]):
        """Subscribe to CDC events on topics matching pattern"""
        consumer = KafkaConsumer(
            topic_pattern,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda m: m.decode('utf-8') if m else None
        )
        self.consumers[topic_pattern] = consumer
        self.callbacks[topic_pattern] = callback
        if self.running:
            self._start_consumer(topic_pattern)
    
    def _start_consumer(self, topic_pattern: str):
        def consume():
            consumer = self.consumers[topic_pattern]
            callback = self.callbacks[topic_pattern]
            for msg in consumer:
                try:
                    callback(msg.value)
                except Exception as e:
                    logger.error(f"CDC callback error: {e}")
        thread = threading.Thread(target=consume, daemon=True)
        thread.start()
        self.threads.append(thread)
    
    def start(self):
        self.running = True
        for topic_pattern in self.consumers:
            self._start_consumer(topic_pattern)
        logger.info("CDC event listener started")
    
    def stop(self):
        self.running = False
        for consumer in self.consumers.values():
            consumer.close()
        for thread in self.threads:
            thread.join(timeout=2)
        logger.info("CDC event listener stopped")

_cdc_listener = None
def get_cdc_listener():
    global _cdc_listener
    if _cdc_listener is None:
        _cdc_listener = CDCEventListener()
    return _cdc_listener
