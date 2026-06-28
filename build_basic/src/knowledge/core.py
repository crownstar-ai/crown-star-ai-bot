# knowledge/core.py – CrownStar Graph Neural Network & Knowledge Graph Engine
import os, json, time, hashlib, numpy as np
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict   # <-- added asdict
from collections import defaultdict
import logging
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Models
# --------------------------------------------------------------------
@dataclass
class Entity:
    id: str
    label: str           # type (e.g., "Person", "Organization", "Concept")
    properties: Dict
    created: int

@dataclass
class Relation:
    id: str
    source_id: str
    target_id: str
    predicate: str       # e.g., "works_for", "located_in", "related_to"
    weight: float = 1.0
    properties: Dict = None

@dataclass
class Triple:
    subject: str
    predicate: str
    object: str

class KnowledgeGraph:
    """In‑memory graph storage with indexing for fast traversal."""
    def __init__(self, storage_dir: str = "data/knowledge/graph"):
        self.storage_dir = storage_dir
        self.entities: Dict[str, Entity] = {}
        self.relations: List[Relation] = []
        self.adj_out: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        self.adj_in: Dict[str, List[Tuple[str, str, float]]] = defaultdict(list)
        self._load()

    def _load(self):
        ent_path = os.path.join(self.storage_dir, "entities.json")
        rel_path = os.path.join(self.storage_dir, "relations.json")
        if os.path.exists(ent_path):
            with open(ent_path, 'r') as f:
                data = json.load(f)
                self.entities = {k: Entity(**v) for k, v in data.items()}
        if os.path.exists(rel_path):
            with open(rel_path, 'r') as f:
                rels = json.load(f)
                for r in rels:
                    self.add_relation(Relation(**r))

    def _save(self):
        os.makedirs(self.storage_dir, exist_ok=True)
        with open(os.path.join(self.storage_dir, "entities.json"), 'w') as f:
            json.dump({k: asdict(v) for k, v in self.entities.items()}, f, indent=2)
        with open(os.path.join(self.storage_dir, "relations.json"), 'w') as f:
            json.dump([asdict(r) for r in self.relations], f, indent=2)

    def add_entity(self, entity: Entity) -> str:
        if entity.id in self.entities:
            return entity.id
        self.entities[entity.id] = entity
        self._save()
        return entity.id

    def add_relation(self, relation: Relation) -> str:
        if relation.source_id not in self.entities or relation.target_id not in self.entities:
            raise ValueError("Source or target entity not found")
        self.relations.append(relation)
        self.adj_out[relation.source_id].append((relation.target_id, relation.predicate, relation.weight))
        self.adj_in[relation.target_id].append((relation.source_id, relation.predicate, relation.weight))
        self._save()
        return relation.id

    def get_neighbors(self, entity_id: str, direction: str = "out") -> List[Tuple[str, str, float]]:
        if direction == "out":
            return self.adj_out.get(entity_id, [])
        else:
            return self.adj_in.get(entity_id, [])

    def query_cypher(self, cypher: str) -> List[Dict]:
        # Placeholder – in production would use actual Cypher parser
        return []

# --------------------------------------------------------------------
# Graph Neural Network Layers
# --------------------------------------------------------------------
class GraphConvolutionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, dropout: float = 0.1):
        super().__init__()
        self.linear = nn.Linear(in_dim, out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, adj):
        x = self.linear(x)
        out = torch.spmm(adj, x) if adj.is_sparse else torch.mm(adj, x)
        out = self.dropout(F.relu(out))
        return out

class GraphAttentionLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, num_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = out_dim // num_heads
        self.linear = nn.Linear(in_dim, out_dim)
        self.att = nn.Parameter(torch.Tensor(1, num_heads, 2 * self.head_dim))
        nn.init.xavier_uniform_(self.att)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, adj):
        N = x.shape[0]
        h = self.linear(x).view(N, self.num_heads, self.head_dim)
        out = h.mean(dim=1)
        return F.relu(out)

class GraphSAGELayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, aggregator: str = "mean"):
        super().__init__()
        self.aggregator = aggregator
        self.linear = nn.Linear(in_dim * 2, out_dim)

    def forward(self, x, adj):
        neighbor_agg = x  # placeholder
        out = torch.cat([x, neighbor_agg], dim=1)
        out = F.relu(self.linear(out))
        return out

class GraphEmbeddingModel(nn.Module):
    def __init__(self, num_nodes: int, node_features_dim: int, hidden_dims: List[int] = [128, 64],
                 output_dim: int = 64, num_layers: int = 2, layer_type: str = "gcn"):
        super().__init__()
        self.num_nodes = num_nodes
        layers = []
        in_dim = node_features_dim
        for i, h in enumerate(hidden_dims):
            if layer_type == "gcn":
                layers.append(GraphConvolutionLayer(in_dim, h))
            elif layer_type == "gat":
                layers.append(GraphAttentionLayer(in_dim, h))
            else:
                layers.append(GraphSAGELayer(in_dim, h))
            in_dim = h
        layers.append(nn.Linear(in_dim, output_dim))
        self.layers = nn.Sequential(*layers)

    def forward(self, x, adj):
        return self.layers(x, adj)

    def get_embeddings(self, x, adj) -> np.ndarray:
        with torch.no_grad():
            emb = self.forward(x, adj)
            return emb.cpu().numpy()

# --------------------------------------------------------------------
# Knowledge Graph Manager
# --------------------------------------------------------------------
class KnowledgeManager:
    def __init__(self, config_path="config/knowledge/config.json"):
        self.config = self._load_config(config_path)
        self.graph = KnowledgeGraph(self.config.get("storage_dir", "data/knowledge/graph"))
        self.gnn_model: Optional[GraphEmbeddingModel] = None
        self.node_embeddings: Dict[str, List[float]] = {}
        self._load_embeddings()

    def _load_config(self, path):
        default = {
            "storage_dir": "data/knowledge/graph",
            "gnn": {
                "enabled": True,
                "layer_type": "gcn",
                "hidden_dims": [128, 64],
                "output_dim": 64,
                "node_features_dim": 128,
                "epochs": 10,
                "learning_rate": 0.001
            },
            "embedding_cache": "data/knowledge/embeddings.npy"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        return default

    def _load_embeddings(self):
        emb_path = self.config.get("embedding_cache")
        if os.path.exists(emb_path):
            data = np.load(emb_path, allow_pickle=True).item()
            self.node_embeddings = data.get("embeddings", {})

    def _save_embeddings(self):
        emb_path = self.config.get("embedding_cache")
        np.save(emb_path, {"embeddings": self.node_embeddings})

    def add_entity(self, entity_id: str, label: str, properties: Dict = None) -> str:
        entity = Entity(id=entity_id, label=label, properties=properties or {}, created=int(time.time()))
        return self.graph.add_entity(entity)

    def add_relation(self, source: str, target: str, predicate: str, weight: float = 1.0, properties: Dict = None) -> str:
        rel = Relation(
            id=hashlib.md5(f"{source}{target}{predicate}".encode()).hexdigest()[:16],
            source_id=source,
            target_id=target,
            predicate=predicate,
            weight=weight,
            properties=properties
        )
        return self.graph.add_relation(rel)

    def train_gnn(self, epochs: int = None) -> Dict:
        if len(self.graph.entities) < 2:
            return {"error": "Need at least 2 entities"}
        node_list = list(self.graph.entities.keys())
        num_nodes = len(node_list)
        node_to_idx = {node: i for i, node in enumerate(node_list)}
        feat_dim = self.config["gnn"]["node_features_dim"]
        x = torch.randn(num_nodes, feat_dim)
        adj = torch.zeros(num_nodes, num_nodes)
        for rel in self.graph.relations:
            i = node_to_idx[rel.source_id]
            j = node_to_idx[rel.target_id]
            adj[i, j] = rel.weight
            adj[j, i] = rel.weight
        deg = adj.sum(dim=1)
        deg_inv_sqrt = torch.pow(deg + 1e-8, -0.5)
        adj_norm = deg_inv_sqrt.view(-1,1) * adj * deg_inv_sqrt.view(1,-1)
        model = GraphEmbeddingModel(
            num_nodes=num_nodes,
            node_features_dim=feat_dim,
            hidden_dims=self.config["gnn"]["hidden_dims"],
            output_dim=self.config["gnn"]["output_dim"],
            layer_type=self.config["gnn"]["layer_type"]
        )
        optimizer = torch.optim.Adam(model.parameters(), lr=self.config["gnn"]["learning_rate"])
        model.train()
        epochs = epochs or self.config["gnn"]["epochs"]
        for epoch in range(epochs):
            optimizer.zero_grad()
            out = model(x, adj_norm)
            loss = F.mse_loss(out, x[:, :self.config["gnn"]["output_dim"]])
            loss.backward()
            optimizer.step()
        model.eval()
        embeddings = model.get_embeddings(x, adj_norm)
        for idx, node in enumerate(node_list):
            self.node_embeddings[node] = embeddings[idx].tolist()
        self._save_embeddings()
        return {"status": "trained", "nodes": num_nodes, "embedding_dim": self.config["gnn"]["output_dim"]}

    def query(self, cypher: str) -> List[Dict]:
        return self.graph.query_cypher(cypher)

    def infer_relations(self, source_entity: str, target_entity: str) -> List[Tuple[str, float]]:
        if source_entity not in self.node_embeddings or target_entity not in self.node_embeddings:
            return []
        emb_src = np.array(self.node_embeddings[source_entity])
        emb_tgt = np.array(self.node_embeddings[target_entity])
        similarity = np.dot(emb_src, emb_tgt) / (np.linalg.norm(emb_src) * np.linalg.norm(emb_tgt) + 1e-8)
        return [("related_to", float(similarity))]

    def get_entity_embedding(self, entity_id: str) -> Optional[List[float]]:
        return self.node_embeddings.get(entity_id)

    def get_graph_stats(self) -> Dict:
        return {
            "entities": len(self.graph.entities),
            "relations": len(self.graph.relations),
            "embedded_entities": len(self.node_embeddings),
            "average_degree": sum(len(v) for v in self.graph.adj_out.values()) / max(1, len(self.graph.entities))
        }

_kg_manager = None
def get_kg_manager():
    global _kg_manager
    if _kg_manager is None:
        _kg_manager = KnowledgeManager()
    return _kg_manager
