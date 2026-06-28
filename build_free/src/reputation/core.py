# reputation/core.py – CrownStar Federated Reputation & Trust Scoring Engine
import os, json, time, hashlib, math, random, threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class TrustEntityType(Enum):
    USER = "user"; AGENT = "agent"; MODEL = "model"; SUBGRAPH = "subgraph"; FUNCTION = "function"

class AttestationType(Enum):
    ENDORSEMENT = "endorsement"; CERTIFICATION = "certification"; COMPLAINT = "complaint"; REVIEW = "review"

@dataclass
class ReputationScore:
    entity_id: str; entity_type: TrustEntityType; overall_score: float; confidence: float
    total_endorsements: int; total_complaints: int; last_updated: int; decay_factor: float = 0.95

@dataclass
class Attestation:
    attestation_id: str; entity_id: str; entity_type: TrustEntityType; attestation_type: AttestationType
    issuer_did: str; rating: float; comment: Optional[str]; timestamp: int; expiry: Optional[int]; metadata: Dict

@dataclass
class SoulboundToken:
    token_id: str; entity_id: str; chain: str; contract_address: str; token_uri: str; minted_at: int; revoked: bool = False

class TrustScorer:
    def __init__(self):
        self.prior_mean = 0.5; self.prior_weight = 10
    def compute_score(self, attestations: List[Attestation], last_score: Optional[float] = None, days_since_last_update: int = 0) -> ReputationScore:
        if not attestations: return self.prior_mean
        total_weight = 0.0; weighted_sum = 0.0; now = int(time.time())
        for att in attestations:
            age_days = (now - att.timestamp) / 86400
            weight = math.exp(-age_days * 0.1)
            weighted_sum += att.rating * weight; total_weight += weight
        if total_weight == 0: return self.prior_mean
        observed_mean = weighted_sum / total_weight
        observed_norm = (observed_mean + 1) / 2
        bayesian_score = (self.prior_mean * self.prior_weight + observed_norm * total_weight) / (self.prior_weight + total_weight)
        if last_score is not None and days_since_last_update > 0:
            decay = 0.95 ** days_since_last_update
            bayesian_score = bayesian_score * decay + last_score * (1 - decay)
        return min(1.0, max(0.0, bayesian_score))
    def confidence(self, num_attestations: int) -> float: return min(1.0, num_attestations / 20.0)

class AttestationStore:
    def __init__(self, storage_dir="data/reputation"):
        self.storage_dir = storage_dir; os.makedirs(storage_dir, exist_ok=True)
        self.attestations: Dict[str, List[Attestation]] = defaultdict(list)
        self.scores: Dict[str, ReputationScore] = {}
        self._load()
    def _load(self):
        att_path = os.path.join(self.storage_dir, "attestations.json")
        if os.path.exists(att_path):
            with open(att_path, 'r') as f:
                data = json.load(f)
                for entity_id, atts in data.items():
                    for a in atts:
                        a["attestation_type"] = AttestationType(a["attestation_type"])
                        self.attestations[entity_id].append(Attestation(**a))
        scores_path = os.path.join(self.storage_dir, "scores.json")
        if os.path.exists(scores_path):
            with open(scores_path, 'r') as f:
                data = json.load(f)
                for k, v in data.items():
                    v["entity_type"] = TrustEntityType(v["entity_type"])
                    self.scores[k] = ReputationScore(**v)
    def _save(self):
        att_data = {eid: [asdict(a) for a in atts] for eid, atts in self.attestations.items()}
        with open(os.path.join(self.storage_dir, "attestations.json"), 'w') as f:
            json.dump(att_data, f, indent=2)
        scores_data = {}
        for k, v in self.scores.items():
            d = asdict(v); d["entity_type"] = v.entity_type.value
            scores_data[k] = d
        with open(os.path.join(self.storage_dir, "scores.json"), 'w') as f:
            json.dump(scores_data, f, indent=2)
    def add_attestation(self, attestation: Attestation):
        self.attestations[attestation.entity_id].append(attestation); self._save()
    def get_attestations(self, entity_id: str) -> List[Attestation]:
        return self.attestations.get(entity_id, [])
    def store_score(self, score: ReputationScore):
        self.scores[score.entity_id] = score; self._save()
    def get_score(self, entity_id: str) -> Optional[ReputationScore]: return self.scores.get(entity_id)

class SoulboundManager:
    def __init__(self, blockchain_manager):
        self.bc = blockchain_manager
    def mint_soulbound_token(self, entity_id: str, chain: str = "ethereum", metadata_uri: str = "") -> SoulboundToken:
        token_id = hashlib.md5(f"sbt_{entity_id}_{time.time()}".encode()).hexdigest()[:16]
        contract_address = "0xSoulboundTokenContract"
        return SoulboundToken(token_id=token_id, entity_id=entity_id, chain=chain, contract_address=contract_address, token_uri=metadata_uri or f"https://crownstar.ai/reputation/{token_id}", minted_at=int(time.time()))
    def revoke_token(self, token_id: str) -> bool: return True

class ReputationOracle:
    def __init__(self, store: AttestationStore):
        self.store = store; self.external_sources = []
    def register_source(self, name: str, endpoint: str): self.external_sources.append((name, endpoint))
    def fetch_external_reputation(self, entity_id: str) -> Optional[float]: return None
    def aggregate(self, entity_id: str) -> ReputationScore:
        local_atts = self.store.get_attestations(entity_id)
        scorer = TrustScorer()
        local_score = scorer.compute_score(local_atts)
        external_score = self.fetch_external_reputation(entity_id)
        combined = local_score * 0.7 + external_score * 0.3 if external_score is not None else local_score
        conf = scorer.confidence(len(local_atts))
        return ReputationScore(entity_id=entity_id, entity_type=TrustEntityType.USER, overall_score=combined, confidence=conf, total_endorsements=sum(1 for a in local_atts if a.rating>0), total_complaints=sum(1 for a in local_atts if a.rating<0), last_updated=int(time.time()))

class ReputationManager:
    def __init__(self, config_path="config/reputation/config.json"):
        self.config = self._load_config(config_path)
        self.store = AttestationStore()
        self.oracle = ReputationOracle(self.store)
        self.soulbound = None
        self._init_soulbound()
    def _load_config(self, path):
        default = {"default_decay_factor":0.95,"prior_mean":0.5,"prior_weight":10,"soulbound_contract":{"ethereum":"0x...","solana":"SBT...","fabric":"soulbound_cc"},"external_sources":[]}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        return default
    def _init_soulbound(self):
        try:
            from blockchain.core import get_bc_manager
            self.soulbound = SoulboundManager(get_bc_manager())
        except: logger.warning("Blockchain manager not available; soulbound tokens disabled"); self.soulbound = None
    def add_attestation(self, attestation: Attestation) -> str:
        self.store.add_attestation(attestation); self.recompute_score(attestation.entity_id, attestation.entity_type); return attestation.attestation_id
    def recompute_score(self, entity_id: str, entity_type: TrustEntityType) -> ReputationScore:
        attestations = self.store.get_attestations(entity_id)
        scorer = TrustScorer()
        old_score = self.store.get_score(entity_id)
        days_since = 0
        if old_score: days_since = max(0, (int(time.time()) - old_score.last_updated) // 86400)
        score_val = scorer.compute_score(attestations, old_score.overall_score if old_score else None, days_since)
        new_score = ReputationScore(entity_id=entity_id, entity_type=entity_type, overall_score=score_val, confidence=scorer.confidence(len(attestations)), total_endorsements=sum(1 for a in attestations if a.rating>0), total_complaints=sum(1 for a in attestations if a.rating<0), last_updated=int(time.time()), decay_factor=self.config["default_decay_factor"])
        self.store.store_score(new_score); return new_score
    def get_score(self, entity_id: str) -> Optional[ReputationScore]:
        score = self.store.get_score(entity_id)
        if not score: return None
        days_since = max(0, (int(time.time()) - score.last_updated) // 86400)
        if days_since > 0:
            decay = score.decay_factor ** days_since
            new_score_val = score.overall_score * decay
            if abs(new_score_val - score.overall_score) > 0.01:
                score.overall_score = new_score_val; score.last_updated = int(time.time()); self.store.store_score(score)
        return score
    def mint_soulbound_token(self, entity_id: str, chain: str = "ethereum", metadata_uri: str = "") -> Optional[SoulboundToken]:
        return self.soulbound.mint_soulbound_token(entity_id, chain, metadata_uri) if self.soulbound else None
    def revoke_soulbound_token(self, token_id: str) -> bool:
        return self.soulbound.revoke_token(token_id) if self.soulbound else False
    def register_external_source(self, name: str, endpoint: str): self.oracle.register_source(name, endpoint)
    def aggregate_reputation(self, entity_id: str) -> ReputationScore: return self.oracle.aggregate(entity_id)

_rep_manager = None
def get_rep_manager():
    global _rep_manager
    if _rep_manager is None: _rep_manager = ReputationManager()
    return _rep_manager
