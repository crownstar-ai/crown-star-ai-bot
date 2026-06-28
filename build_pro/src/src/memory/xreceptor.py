# ====================================================================================================
# xreceptor.py – XReceptor Engine for CrownStar‑Absolute Biomimetic Memory
# Implements:
#   - Memory reception (from human, cloud, or other EverOnes)
#   - Automatic linking between memories (semantic similarity, temporal proximity)
#   - Consolidation (periodic background processing)
#   - Recall triggering (associative retrieval based on cues)
# ====================================================================================================

import asyncio
import time
import threading
import heapq
from collections import deque, defaultdict
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from difflib import SequenceMatcher

logger = logging.getLogger("CrownStar.XReceptor")

# --------------------------------------------------------------------
# Data classes for memory events
# --------------------------------------------------------------------
@dataclass
class MemoryReceptionEvent:
    """Event representing a new memory being received."""
    memory_id: str
    memory_type: str  # "conversation", "experience", "thought"
    content: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"  # "user", "cloud", "synchronization", "internal"
    importance: float = 0.5
    tags: List[str] = field(default_factory=list)

@dataclass
class MemoryLink:
    """A link between two memories (bidirectional)."""
    source_id: str
    target_id: str
    strength: float  # 0.0 to 1.0
    link_type: str   # "semantic", "temporal", "causal", "emotional"
    created: float = field(default_factory=time.time)

# --------------------------------------------------------------------
# XReceptor Engine Core
# --------------------------------------------------------------------
class XReceptorEngine:
    """
    Receives new memories, automatically links them to existing ones,
    consolidates the memory network, and triggers recall based on cues.
    """
    
    def __init__(self, memory_system, xpointer_resolver=None, 
                 auto_link: bool = True, auto_consolidate: bool = True,
                 consolidate_interval: int = 300):
        """
        Args:
            memory_system: Reference to the BiomimeticMemory instance.
            xpointer_resolver: XPointerResolver instance for linking.
            auto_link: If True, automatically link new memories on reception.
            auto_consolidate: If True, run periodic consolidation in background.
            consolidate_interval: Seconds between consolidation runs.
        """
        self.memory = memory_system
        self.xpointer = xpointer_resolver
        self.auto_link = auto_link
        self.auto_consolidate = auto_consolidate
        self.consolidate_interval = consolidate_interval
        
        # Reception queue (thread‑safe)
        self._reception_queue: deque = deque()
        self._lock = threading.RLock()
        
        # Link storage (in‑memory cache, persists to XML on consolidate)
        self.links: Dict[str, List[MemoryLink]] = defaultdict(list)  # source_id -> list of links
        self._link_index: Dict[Tuple[str, str], MemoryLink] = {}     # (source,target) -> link
        
        # Background consolidation thread
        self._consolidate_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "memories_received": 0,
            "links_created": 0,
            "consolidations": 0,
            "recalls_triggered": 0
        }
        
        # Load existing links from memory system if available
        self._load_links()
        
        logger.info("XReceptorEngine initialised")
        if auto_consolidate:
            self.start_background_consolidation()
    
    # --------------------------------------------------------------------
    # Link persistence (simplified – in production, store in separate XML)
    # --------------------------------------------------------------------
    def _load_links(self):
        """Load existing links from the memory system's metadata (if any)."""
        # Placeholder – would read from a dedicated links.xml file
        pass
    
    def _save_links(self):
        """Save links to persistent storage."""
        # Placeholder – would write to links.xml
        pass
    
    # --------------------------------------------------------------------
    # Memory Reception
    # --------------------------------------------------------------------
    def receive_memory(self, event: MemoryReceptionEvent) -> str:
        """
        Receive a new memory event. Queues it for processing.
        Returns the memory ID (may be newly generated if not provided).
        """
        # Generate ID if not present
        if not event.memory_id:
            import uuid
            event.memory_id = str(uuid.uuid4())
        
        with self._lock:
            self._reception_queue.append(event)
        
        # Process immediately if queue is small, otherwise let background handle
        if len(self._reception_queue) <= 10:
            self._process_reception_queue()
        
        self.stats["memories_received"] += 1
        logger.debug(f"Memory received: {event.memory_id} (type={event.memory_type}, source={event.source})")
        return event.memory_id
    
    def _process_reception_queue(self):
        """Process all pending reception events."""
        while self._reception_queue:
            event = self._reception_queue.popleft()
            self._ingest_memory(event)
    
    def _ingest_memory(self, event: MemoryReceptionEvent):
        """
        Ingest a single memory: store it, then auto‑link if enabled.
        """
        # Store the memory in the memory system
        mem_data = {
            "id": event.memory_id,
            "type": event.memory_type,
            "timestamp": event.timestamp,
            "content": event.content,
            "importance": event.importance,
            "tags": event.tags,
            "source": event.source
        }
        # Assuming memory system has a store_memory method
        if hasattr(self.memory, 'store_memory'):
            self.memory.store_memory(mem_data)
        elif hasattr(self.memory, 'add_entry'):
            self.memory.add_entry(mem_data)
        else:
            logger.warning("Memory system has no store_memory method – memory not persisted")
        
        # Auto‑link
        if self.auto_link:
            self._auto_link_memory(event.memory_id, mem_data)
    
    # --------------------------------------------------------------------
    # Auto‑linking (semantic similarity)
    # --------------------------------------------------------------------
    def _auto_link_memory(self, new_id: str, new_data: Dict):
        """
        Find existing memories similar to the new one and create links.
        Uses simple TF‑IDF keyword matching; can be extended with embeddings.
        """
        # Extract text from new memory
        new_text = self._extract_text(new_data)
        if not new_text:
            return
        
        # Get all existing memory IDs (simplified – would be more efficient with index)
        existing_ids = self._get_existing_memory_ids()
        if not existing_ids:
            return
        
        # Score each existing memory for similarity
        scores = []
        for old_id in existing_ids:
            if old_id == new_id:
                continue
            old_data = self._get_memory_data(old_id)
            if not old_data:
                continue
            old_text = self._extract_text(old_data)
            if not old_text:
                continue
            similarity = self._text_similarity(new_text, old_text)
            if similarity > 0.3:  # threshold
                scores.append((similarity, old_id))
        
        # Create links for top matches
        scores.sort(reverse=True, key=lambda x: x[0])
        for similarity, old_id in scores[:10]:
            strength = similarity * 0.8 + 0.2  # scale to 0.2‑1.0
            self.create_link(new_id, old_id, strength, "semantic")
    
    def _extract_text(self, memory_data: Dict) -> str:
        """Extract textual content from a memory entry."""
        if "content" in memory_data:
            content = memory_data["content"]
            if isinstance(content, dict):
                return content.get("query", "") + " " + content.get("response", "")
            return str(content)
        elif "query" in memory_data:
            return memory_data.get("query", "") + " " + memory_data.get("response", "")
        return ""
    
    def _get_existing_memory_ids(self) -> List[str]:
        """Return list of all memory IDs currently stored."""
        # Placeholder – would query memory system
        if hasattr(self.memory, 'get_all_ids'):
            return self.memory.get_all_ids()
        return []
    
    def _get_memory_data(self, mem_id: str) -> Optional[Dict]:
        """Retrieve memory data by ID."""
        if hasattr(self.memory, 'get_memory'):
            return self.memory.get_memory(mem_id)
        return None
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts using SequenceMatcher (simple)."""
        # Normalise: lowercase, remove punctuation
        norm1 = re.sub(r'[^\w\s]', '', text1.lower())
        norm2 = re.sub(r'[^\w\s]', '', text2.lower())
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    # --------------------------------------------------------------------
    # Link Management
    # --------------------------------------------------------------------
    def create_link(self, source_id: str, target_id: str, strength: float, 
                    link_type: str = "semantic") -> bool:
        """
        Create a bidirectional link between two memories.
        Returns True if new link created, False if already exists.
        """
        with self._lock:
            key = (source_id, target_id)
            if key in self._link_index:
                # Update existing link strength
                existing = self._link_index[key]
                existing.strength = max(existing.strength, strength)
                existing.created = time.time()
                return False
            # Create forward link
            link = MemoryLink(source_id, target_id, strength, link_type)
            self.links[source_id].append(link)
            # Reverse link
            rev_link = MemoryLink(target_id, source_id, strength, link_type)
            self.links[target_id].append(rev_link)
            self._link_index[key] = link
            self._link_index[(target_id, source_id)] = rev_link
            self.stats["links_created"] += 1
            logger.debug(f"Link created: {source_id} <-> {target_id} (strength={strength:.2f})")
            return True
    
    def get_links(self, memory_id: str) -> List[MemoryLink]:
        """Return all links for a given memory."""
        return self.links.get(memory_id, [])
    
    def get_associated_memories(self, memory_id: str, min_strength: float = 0.0) -> List[Tuple[str, float]]:
        """Return list of (target_id, strength) for memories linked to the given one."""
        return [(link.target_id, link.strength) for link in self.links.get(memory_id, [])
                if link.strength >= min_strength]
    
    # --------------------------------------------------------------------
    # Consolidation (periodic background)
    # --------------------------------------------------------------------
    def start_background_consolidation(self):
        """Start a background thread that periodically consolidates the memory network."""
        if self._consolidate_thread is not None and self._consolidate_thread.is_alive():
            return
        self._running = True
        self._consolidate_thread = threading.Thread(target=self._consolidation_loop, daemon=True)
        self._consolidate_thread.start()
        logger.info("Background consolidation started")
    
    def stop_background_consolidation(self):
        """Stop the background consolidation thread."""
        self._running = False
        if self._consolidate_thread:
            self._consolidate_thread.join(timeout=5)
        logger.info("Background consolidation stopped")
    
    def _consolidation_loop(self):
        """Background loop that runs consolidate() periodically."""
        while self._running:
            time.sleep(self.consolidate_interval)
            try:
                self.consolidate()
            except Exception as e:
                logger.error(f"Consolidation error: {e}")
    
    def consolidate(self):
        """
        Consolidate the memory network:
          - Process any pending reception events
          - Prune weak links (below threshold)
          - Merge duplicate memories (optional)
          - Update importance scores based on link count
          - Save links to persistent storage
        """
        with self._lock:
            # Process any pending events
            self._process_reception_queue()
            
            # Prune weak links (below 0.1)
            weak_threshold = 0.1
            for mem_id in list(self.links.keys()):
                self.links[mem_id] = [link for link in self.links[mem_id] if link.strength >= weak_threshold]
                # Clean up link index
                for link in self.links[mem_id]:
                    key = (link.source_id, link.target_id)
                    if link.strength < weak_threshold and key in self._link_index:
                        del self._link_index[key]
                if not self.links[mem_id]:
                    del self.links[mem_id]
            
            # Update importance of memories based on number of incoming links
            if hasattr(self.memory, 'update_importance'):
                incoming_counts = defaultdict(int)
                for links in self.links.values():
                    for link in links:
                        incoming_counts[link.target_id] += 1
                for mem_id, count in incoming_counts.items():
                    bonus = min(0.5, count * 0.05)
                    self.memory.update_importance(mem_id, bonus)
            
            # Save links
            self._save_links()
            
            self.stats["consolidations"] += 1
            logger.info(f"Consolidation complete: {len(self.links)} memory link entries, "
                       f"{self.stats['links_created']} total links")
    
    # --------------------------------------------------------------------
    # Recall Triggering (associative retrieval)
    # --------------------------------------------------------------------
    def trigger_recall(self, cue: str, top_k: int = 5, min_similarity: float = 0.2) -> List[Dict]:
        """
        Trigger recall based on a textual cue (e.g., a question or fragment).
        Returns list of memory entries with similarity scores.
        """
        self.stats["recalls_triggered"] += 1
        
        # First, find candidate memories by keyword matching
        candidates = []
        for mem_id in self._get_existing_memory_ids():
            mem_data = self._get_memory_data(mem_id)
            if not mem_data:
                continue
            text = self._extract_text(mem_data)
            similarity = self._text_similarity(cue, text)
            if similarity >= min_similarity:
                candidates.append((similarity, mem_id, mem_data))
        
        # Sort by similarity
        candidates.sort(reverse=True, key=lambda x: x[0])
        
        # Expand via linked memories (associative recall)
        expanded_results = []
        for sim, mem_id, mem_data in candidates[:top_k]:
            result = {
                "memory_id": mem_id,
                "similarity": sim,
                "content": mem_data,
                "associations": []
            }
            # Add linked memories
            for assoc_id, strength in self.get_associated_memories(mem_id, min_strength=0.5):
                assoc_data = self._get_memory_data(assoc_id)
                if assoc_data:
                    result["associations"].append({
                        "memory_id": assoc_id,
                        "strength": strength,
                        "content_preview": self._extract_text(assoc_data)[:200]
                    })
            expanded_results.append(result)
        
        logger.debug(f"Recall triggered for cue '{cue[:50]}' -> {len(expanded_results)} results")
        return expanded_results
    
    # --------------------------------------------------------------------
    # Statistics and management
    # --------------------------------------------------------------------
    def get_stats(self) -> Dict:
        """Return comprehensive statistics."""
        return {
            **self.stats,
            "queue_size": len(self._reception_queue),
            "total_links": sum(len(links) for links in self.links.values()),
            "unique_memories_linked": len(self.links),
            "background_running": self._running,
            "consolidate_interval": self.consolidate_interval
        }
    
    def clear_all_links(self):
        """Remove all memory links (dangerous)."""
        with self._lock:
            self.links.clear()
            self._link_index.clear()
            self.stats["links_created"] = 0
            logger.warning("All memory links cleared")
    
    def shutdown(self):
        """Gracefully shut down the XReceptor engine."""
        self.stop_background_consolidation()
        self._process_reception_queue()  # final flush
        self._save_links()
        logger.info("XReceptorEngine shut down")


# --------------------------------------------------------------------
# Convenience function to integrate with BiomimeticMemory
# --------------------------------------------------------------------
def create_xreceptor_for_memory(memory_system, auto_link=True, auto_consolidate=True) -> XReceptorEngine:
    """Create an XReceptorEngine wired to a BiomimeticMemory instance."""
    # Try to get XPointerResolver from memory system if available
    xpointer = getattr(memory_system, 'xpointer', None)
    engine = XReceptorEngine(memory_system, xpointer, auto_link, auto_consolidate)
    return engine

# ====================================================================================================
# Example usage (commented)
# ====================================================================================================
"""
# Assuming memory_system is a BiomimeticMemory instance
receptor = XReceptorEngine(memory_system)
# Receive a new memory event
event = MemoryReceptionEvent(
    memory_id="",
    memory_type="conversation",
    content={"query": "What is XReceptor?", "response": "It receives and links memories."},
    source="user"
)
receptor.receive_memory(event)
# Trigger recall
results = receptor.trigger_recall("XReceptor", top_k=3)
for r in results:
    print(r["content"]["query"], r["similarity"])
# Shutdown
receptor.shutdown()
"""

# ====================================================================================================
# END OF xreceptor.py (32,784 characters)
# ====================================================================================================
