# pipeline/api.py – REST API for data pipeline
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List
import json
from .kafka.kafka_service import get_kafka_pipeline
from .spark.spark_streaming import get_spark_job
from .flink.flink_jobs import get_flink_job_manager
from .schemas.event_schemas import CrownStarEvent
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/pipeline", tags=["Data Pipeline"])

class ProduceEventRequest(BaseModel):
    topic_key: str
    event: Dict
    key: Optional[str] = None

class SparkStreamRequest(BaseModel):
    job_type: str  # cost_aggregation, conversation_embedding
    input_topic: str
    output_topic: Optional[str] = None

class FlinkJobRequest(BaseModel):
    job_type: str  # sql, jar
    sql_statement: Optional[str] = None
    jar_path: Optional[str] = None
    main_class: Optional[str] = None
    job_name: str = "crownstar_job"

@router.post("/events")
async def produce_event(req: ProduceEventRequest, user: dict = Depends(require_permission("admin"))):
    kafka = get_kafka_pipeline()
    success = kafka.produce(req.topic_key, req.event, req.key)
    if success:
        return {"message": "Event produced", "topic": req.topic_key}
    raise HTTPException(500, "Failed to produce event")

@router.get("/kafka/status")
async def kafka_status(user: dict = Depends(require_permission("admin"))):
    kafka = get_kafka_pipeline()
    return kafka.get_status()

@router.post("/spark/stream")
async def start_spark_stream(req: SparkStreamRequest, user: dict = Depends(require_permission("admin"))):
    spark = get_spark_job()
    kafka_bootstrap = get_kafka_pipeline().config["bootstrap_servers"][0]
    if req.job_type == "cost_aggregation":
        if not req.output_topic:
            raise HTTPException(400, "output_topic required for cost_aggregation")
        query = spark.create_usage_aggregation_stream(kafka_bootstrap, req.input_topic, req.output_topic)
        return {"job_id": query.id, "message": "Spark stream started"}
    elif req.job_type == "conversation_embedding":
        query = spark.create_conversation_embedding_stream(kafka_bootstrap, req.input_topic)
        return {"job_id": query.id, "message": "Spark stream started"}
    else:
        raise HTTPException(400, "Unknown job_type")

@router.get("/spark/jobs")
async def list_spark_jobs(user: dict = Depends(require_permission("admin"))):
    spark = get_spark_job()
    return {"streams": [{"id": q.id, "name": q.name, "status": q.status} for q in spark.streams]}

@router.post("/flink/job")
async def submit_flink_job(req: FlinkJobRequest, user: dict = Depends(require_permission("admin"))):
    flink = get_flink_job_manager()
    if req.job_type == "sql":
        job_id = flink.submit_sql_job(req.sql_statement, req.job_name)
        return {"job_id": job_id}
    elif req.job_type == "jar":
        if not req.jar_path or not req.main_class:
            raise HTTPException(400, "jar_path and main_class required for jar job")
        job_id = flink.submit_jar_job(req.jar_path, req.main_class)
        return {"job_id": job_id}
    else:
        raise HTTPException(400, "Unknown job_type")

@router.get("/flink/jobs")
async def list_flink_jobs(user: dict = Depends(require_permission("admin"))):
    flink = get_flink_job_manager()
    return {"jobs": flink.list_jobs()}

@router.post("/test/event")
async def send_test_event(user: dict = Depends(require_permission("admin"))):
    event = CrownStarEvent.user_action("test_user", "default", "test_action", {"source": "api"})
    kafka = get_kafka_pipeline()
    success = kafka.produce("user_actions", event)
    return {"sent": success, "event": event}
