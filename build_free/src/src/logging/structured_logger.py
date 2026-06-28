# logging/structured_logger.py – JSON logger with Loki integration
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any
from pythonjsonlogger import jsonlogger

class CrownStarJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'trace_id'):
            log_record['trace_id'] = record.trace_id

def setup_json_logging(level=logging.INFO):
    """Configure root logger to output JSON to stdout (for Loki)"""
    handler = logging.StreamHandler(sys.stdout)
    formatter = CrownStarJsonFormatter('%(timestamp)s %(level)s %(name)s %(message)s')
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    # Disable default stderr handler
    root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, logging.StreamHandler)]
    root_logger.addHandler(handler)
    return root_logger

class RequestContextFilter(logging.Filter):
    def __init__(self, request_id_key: str = 'request_id'):
        super().__init__()
        self.request_id_key = request_id_key
    
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        if not hasattr(record, 'trace_id'):
            record.trace_id = 'N/A'
        return True

def get_logger(name: str):
    logger = logging.getLogger(name)
    # Ensure JSON format
    if not any(isinstance(h.formatter, CrownStarJsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CrownStarJsonFormatter())
        logger.addHandler(handler)
    return logger
