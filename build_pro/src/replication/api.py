# replication/api.py – REST API for CDC and replication
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
from .kafka_connect.connect_client import get_connect_client
from .debezium.connector_configs import DebeziumConnectorBuilder
from .cdc.event_listener import get_cdc_listener
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/replication", tags=["Replication"])

class CreateConnectorRequest(BaseModel):
    name: str
    database_type: str  # postgresql, mysql, sqlserver
    host: str
    port: int
    database: str
    user: str
    password: str
    tables: Optional[str] = None  # comma-separated list

@router.get("/cdc/status")
async def cdc_status(user: dict = Depends(require_permission("admin"))):
    listener = get_cdc_listener()
    return {
        "running": listener.running,
        "subscribed_topics": list(listener.consumers.keys()),
        "threads": len(listener.threads)
    }

@router.get("/connectors")
async def list_connectors(user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    connectors = client.list_connectors()
    return {"connectors": connectors}

@router.get("/connectors/{name}")
async def get_connector(name: str, user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    connector = client.get_connector(name)
    if not connector:
        raise HTTPException(404, "Connector not found")
    status = client.get_connector_status(name)
    return {"connector": connector, "status": status}

@router.post("/connectors")
async def create_connector(req: CreateConnectorRequest, background: BackgroundTasks, user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    if req.database_type == "postgresql":
        config = DebeziumConnectorBuilder.postgresql(
            req.name, req.host, req.port, req.database, req.user, req.password,
            table_include_list=req.tables
        )
    elif req.database_type == "mysql":
        config = DebeziumConnectorBuilder.mysql(
            req.name, req.host, req.port, req.database, req.user, req.password,
            table_include_list=req.tables
        )
    elif req.database_type == "sqlserver":
        config = DebeziumConnectorBuilder.sqlserver(
            req.name, req.host, req.port, req.database, req.user, req.password,
            schema_include_list=req.tables
        )
    else:
        raise HTTPException(400, "Unsupported database type")
    try:
        result = client.create_connector(req.name, config)
        return {"message": f"Connector {req.name} created", "result": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.delete("/connectors/{name}")
async def delete_connector(name: str, user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    if client.delete_connector(name):
        return {"message": f"Connector {name} deleted"}
    raise HTTPException(404, "Connector not found")

@router.post("/connectors/{name}/pause")
async def pause_connector(name: str, user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    if client.pause_connector(name):
        return {"message": f"Connector {name} paused"}
    raise HTTPException(404, "Connector not found")

@router.post("/connectors/{name}/resume")
async def resume_connector(name: str, user: dict = Depends(require_permission("admin"))):
    client = get_connect_client()
    if client.resume_connector(name):
        return {"message": f"Connector {name} resumed"}
    raise HTTPException(404, "Connector not found")

@router.post("/cdc/start")
async def start_cdc(user: dict = Depends(require_permission("admin"))):
    listener = get_cdc_listener()
    listener.start()
    return {"message": "CDC event listener started"}

@router.post("/cdc/stop")
async def stop_cdc(user: dict = Depends(require_permission("admin"))):
    listener = get_cdc_listener()
    listener.stop()
    return {"message": "CDC event listener stopped"}

@router.get("/cdc/events")
async def get_cdc_events(topic: str, limit: int = 10, user: dict = Depends(require_permission("admin"))):
    # Retrieve recent events from Kafka topic (simplified)
    # In production, would query Kafka directly
    return {"topic": topic, "events": [], "message": "Use Kafka consumer to fetch events"}
