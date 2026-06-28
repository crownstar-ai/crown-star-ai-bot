# graphql/core.py – CrownStar GraphQL Federation & API Gateway
import os, json, time, hashlib, uuid, asyncio, threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import requests

logger = logging.getLogger(__name__)

try:
    from graphql import (
        build_schema, graphql, parse, validate, execute,
        GraphQLSchema, GraphQLObjectType, GraphQLField, GraphQLString,
        GraphQLInt, GraphQLFloat, GraphQLBoolean, GraphQLList, GraphQLNonNull
    )
    GRAPHQL_AVAILABLE = True
except ImportError:
    GRAPHQL_AVAILABLE = False
    logger.warning("graphql-core not installed. Install with: pip install graphql-core")

@dataclass
class SubgraphDefinition:
    subgraph_id: str; name: str; url: str; schema_sdl: str; version: int
    active: bool; created_at: int; updated_at: int

@dataclass
class GatewayRoute:
    path: str; subgraph_id: str; methods: List[str]; rate_limit_per_second: int
    cost_per_request: float; require_auth: bool

@dataclass
class GraphQLRequest:
    query: str; variables: Dict; operation_name: Optional[str]; headers: Dict; client_id: str

@dataclass
class GraphQLResponse:
    data: Optional[Dict]; errors: Optional[List[Dict]]; extensions: Dict

class SchemaComposer:
    def __init__(self): self.subgraphs: Dict[str, SubgraphDefinition] = {}
    def add_subgraph(self, subgraph: SubgraphDefinition): self.subgraphs[subgraph.subgraph_id] = subgraph
    def compose(self) -> str:
        merged_sdl = "extend schema @link(url: \"https://specs.apollo.dev/federation/v2.3\", import: [\"@key\", \"@external\", \"@provides\", \"@requires\", \"@shareable\"])\n"
        for sub in self.subgraphs.values():
            if sub.active:
                merged_sdl += f"# Subgraph: {sub.name}\n{sub.schema_sdl}\n\n"
        return merged_sdl
    def get_subgraph_for_entity(self, type_name: str, field: str) -> Optional[str]:
        for sub in self.subgraphs.values():
            if sub.active: return sub.subgraph_id
        return None

class QueryPlanner:
    def __init__(self, composer: SchemaComposer):
        self.composer = composer; self.supergraph_schema = None
    def build_supergraph_schema(self):
        supergraph_sdl = self.composer.compose()
        if GRAPHQL_AVAILABLE: self.supergraph_schema = build_schema(supergraph_sdl)
        return self.supergraph_schema
    def plan(self, query: str) -> List[Dict]:
        plans = []
        for sub_id, sub in self.composer.subgraphs.items():
            if sub.active:
                plans.append({"subgraph_id": sub_id, "subquery": query, "variables": {}})
        return plans

class FederatedExecutor:
    def __init__(self, composer: SchemaComposer, planner: QueryPlanner):
        self.composer = composer; self.planner = planner
    async def execute(self, request: GraphQLRequest) -> GraphQLResponse:
        if not self.planner.supergraph_schema: self.planner.build_supergraph_schema()
        plans = self.planner.plan(request.query)
        results = {}; errors = []
        async def fetch_subgraph(plan):
            sub = self.composer.subgraphs.get(plan["subgraph_id"])
            if not sub: return None, {"message": f"Subgraph {plan['subgraph_id']} not found"}
            try:
                resp = await asyncio.to_thread(requests.post, sub.url, json={"query": plan["subquery"], "variables": request.variables}, headers=request.headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json(); return data.get("data"), None
                else: return None, {"message": f"Subgraph error: {resp.status_code}"}
            except Exception as e: return None, {"message": str(e)}
        tasks = [fetch_subgraph(plan) for plan in plans]
        for task in tasks:
            data, err = await task
            if err: errors.append(err)
            elif data: results.update(data)
        return GraphQLResponse(data=results if results else None, errors=errors if errors else None, extensions={"plans": len(plans)})

class APIGateway:
    def __init__(self):
        self.routes: Dict[str, GatewayRoute] = {}
        self._rate_limiters: Dict[str, float] = {}
    def add_route(self, route: GatewayRoute): self.routes[route.path] = route
    def authorize(self, path: str, headers: Dict) -> bool:
        route = self.routes.get(path)
        if not route or not route.require_auth: return True
        api_key = headers.get("X-API-Key")
        return api_key is not None
    def check_rate_limit(self, path: str, client_id: str) -> bool:
        route = self.routes.get(path)
        if not route: return True
        key = f"{path}:{client_id}"; now = time.time()
        last = self._rate_limiters.get(key, 0)
        if now - last < (1.0 / route.rate_limit_per_second): return False
        self._rate_limiters[key] = now; return True
    def record_cost(self, path: str, client_id: str):
        route = self.routes.get(path)
        if route:
            try:
                requests.post("http://localhost:8080/v1/cost/metrics", json={"resource_id": f"gateway_{path}","resource_type":"api","provider":"local","region":"global","hourly_cost":route.cost_per_request/3600.0,"utilization_cpu":0,"utilization_memory":0,"utilization_disk":0,"timestamp":int(time.time())}, timeout=1)
            except: pass

class GraphQLFederationManager:
    def __init__(self, config_path="config/graphql/config.json"):
        self.config = self._load_config(config_path)
        self.composer = SchemaComposer()
        self.planner = QueryPlanner(self.composer)
        self.executor = FederatedExecutor(self.composer, self.planner)
        self.gateway = APIGateway()
        self._load_subgraphs()
    def _load_config(self, path):
        default = {"gateway_port":8080,"default_rate_limit":100,"default_cost_per_request":0.00001,"subgraphs_dir":"data/graphql/subgraphs"}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        os.makedirs(default["subgraphs_dir"], exist_ok=True)
        return default
    def _load_subgraphs(self):
        sub_dir = self.config["subgraphs_dir"]
        for fname in os.listdir(sub_dir):
            if fname.endswith(".json"):
                with open(os.path.join(sub_dir, fname),'r') as f:
                    data = json.load(f)
                    sub = SubgraphDefinition(**data)
                    self.composer.add_subgraph(sub)
                    route = GatewayRoute(path=f"/graphql/{sub.name}", subgraph_id=sub.subgraph_id, methods=["POST"], rate_limit_per_second=self.config["default_rate_limit"], cost_per_request=self.config["default_cost_per_request"], require_auth=True)
                    self.gateway.add_route(route)
    def register_subgraph(self, subgraph: SubgraphDefinition) -> str:
        subgraph.subgraph_id = str(uuid.uuid4())[:8]
        subgraph.created_at = int(time.time())
        subgraph.updated_at = subgraph.created_at
        self.composer.add_subgraph(subgraph)
        with open(os.path.join(self.config["subgraphs_dir"], f"{subgraph.subgraph_id}.json"),'w') as f:
            json.dump(asdict(subgraph), f, indent=2)
        self.planner.build_supergraph_schema()
        return subgraph.subgraph_id
    async def federated_query(self, query: str, variables: Dict, headers: Dict, client_id: str) -> GraphQLResponse:
        path = "/graphql"
        if not self.gateway.authorize(path, headers):
            return GraphQLResponse(data=None, errors=[{"message":"Unauthorized"}], extensions={})
        if not self.gateway.check_rate_limit(path, client_id):
            return GraphQLResponse(data=None, errors=[{"message":"Rate limit exceeded"}], extensions={})
        request = GraphQLRequest(query=query, variables=variables, operation_name=None, headers=headers, client_id=client_id)
        response = await self.executor.execute(request)
        self.gateway.record_cost(path, client_id)
        return response
    def get_subgraphs(self) -> List[Dict]: return [asdict(s) for s in self.composer.subgraphs.values()]
    def get_supergraph_sdl(self) -> str: return self.composer.compose()

_graphql_manager = None
def get_graphql_manager():
    global _graphql_manager
    if _graphql_manager is None: _graphql_manager = GraphQLFederationManager()
    return _graphql_manager
