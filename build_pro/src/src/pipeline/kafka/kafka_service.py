# pipeline/kafka/kafka_service.py – Kafka producer and consumer
import json
import os
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import NoBrokersAvailable
import logging

logger = logging.getLogger("crownstar.pipeline.kafka")

class KafkaPipeline:
    def __init__(self, config_path: str = "config/pipeline/kafka.json"):
        self.config = self._load_config(config_path)
        self.producer = None
        self.consumers = {}
        self._connect()
    
    def _load_config(self, path):
        default = {
            "bootstrap_servers": ["localhost:9092"],
            "client_id": "crownstar",
            "topics": {
                "user_actions": "crownstar.user_actions",
                "model_inference": "crownstar.model_inference",
                "cost_events": "crownstar.cost_events",
                "conversations": "crownstar.conversations",
                "alerts": "crownstar.alerts"
            },
            "consumer_group": "crownstar_consumer"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default
    
    def _connect(self):
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config["client_id"],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
            logger.info("Kafka producer connected")
        except NoBrokersAvailable:
            logger.warning("Kafka broker not available – producer disabled")
            self.producer = None
    
    def produce(self, topic_key: str, value: Dict, key: str = None) -> bool:
        """Produce event to specified topic"""
        if not self.producer:
            return False
        topic = self.config["topics"].get(topic_key)
        if not topic:
            logger.error(f"Unknown topic key: {topic_key}")
            return False
        try:
            future = self.producer.send(topic, value=value, key=key.encode() if key else None)
            future.get(timeout=5)
            logger.debug(f"Produced event to {topic}: {value}")
            return True
        except Exception as e:
            logger.error(f"Failed to produce event: {e}")
            return False
    
    def consume(self, topic_key: str, callback: Callable, group_id: str = None):
        """Start consumer for a topic (runs in background thread)"""
        topic = self.config["topics"].get(topic_key)
        if not topic:
            raise ValueError(f"Unknown topic key: {topic_key}")
        group = group_id or self.config["consumer_group"]
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.config["bootstrap_servers"],
            group_id=group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )
        def consume_loop():
            for msg in consumer:
                try:
                    callback(msg.value)
                except Exception as e:
                    logger.error(f"Consumer callback error: {e}")
        thread = threading.Thread(target=consume_loop, daemon=True)
        thread.start()
        self.consumers[topic_key] = {"consumer": consumer, "thread": thread}
        logger.info(f"Started consumer for topic {topic}")
    
    def get_status(self) -> Dict:
        return {
            "producer_connected": self.producer is not None,
            "consumers": list(self.consumers.keys()),
            "topics": self.config["topics"]
        }

_kafka = None
def get_kafka_pipeline():
    global _kafka
    if _kafka is None:
        _kafka = KafkaPipeline()
    return _kafka
