# gateway/federation/gateway.py – Federated GraphQL gateway (Apollo Router or custom)
import asyncio
import httpx
from typing import Dict, Any
import json
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from strawberry.fastapi import GraphQLRouter
from strawberry.federation import Schema

# Import subgraph schemas (for composition)
from ..graphql.subgraphs.chat import schema as chat_schema
from ..graphql.subgraphs.users import schema as users_schema
from ..graphql.subgraphs.models import schema as models_schema
from ..graphql.subgraphs.analytics import schema as analytics_schema

# Compose federated schema (simplified – would use federation directive merging)
composed_schema = strawberry.federation.Schema(
    query=chat_schema.query_type,
    mutation=None
)

graphql_app = GraphQLRouter(composed_schema)

# Apollo Router config (if using external router)
APOLLO_ROUTER_URL = "http://localhost:4000"  # default

class FederatedGateway:
    def __init__(self):
        self.subgraphs = {
            "chat": "http://localhost:8081/graphql",
            "users": "http://localhost:8082/graphql",
            "models": "http://localhost:8083/graphql",
            "analytics": "http://localhost:8084/graphql"
        }
        self.client = httpx.AsyncClient()
    
    async def query(self, query: str, variables: Dict = None, headers: Dict = None) -> Dict:
        # Route to appropriate subgraph based on query root field
        # Simplified: send to chat subgraph for demo
        subgraph = self._select_subgraph(query)
        target = self.subgraphs.get(subgraph, self.subgraphs["chat"])
        resp = await self.client.post(
            target,
            json={"query": query, "variables": variables or {}},
            headers=headers or {}
        )
        return resp.json()
    
    def _select_subgraph(self, query: str) -> str:
        if "conversation" in query or "messages" in query:
            return "chat"
        if "user" in query or "users" in query:
            return "users"
        if "model" in query or "models" in query:
            return "models"
        if "usage" in query:
            return "analytics"
        return "chat"

_federated_gateway = FederatedGateway()
