# src/memory/memory_integration.py
"""
Complete memory integration for CrownStar.
Manages chat context, vector retrieval, and memory persistence.
"""

import json
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime

from src.core.logging_config import get_logger
from src.core.exceptions import DatabaseError
from src.database.connection import get_db_connection
from src.memory.vector_store import VectorStore

logger = get_logger(__name__)


class MemoryManager:
    """Integrates all memory systems into a single interface."""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def create_chat(self, project_id: Optional[str] = None, title: str = "") -> str:
        """Create a new chat session."""
        chat_id = str(uuid.uuid4())[:8]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_sessions (id, project_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (chat_id, project_id, title, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
            conn.commit()
        logger.info(f"Created chat session: {chat_id} (project={project_id})")
        return chat_id
    
    def save_message(self, chat_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        """Save a message to memory and optionally to vector index."""
        msg_id = str(uuid.uuid4())[:12]
        metadata_json = json.dumps(metadata or {})
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_messages (id, chat_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg_id, chat_id, role, content, metadata_json, datetime.utcnow().isoformat()))
            conn.commit()
        
        # Optionally add to vector index for semantic search
        # (skip for now; will be added later)
        
        logger.debug(f"Saved message {msg_id} in chat {chat_id}")
        return msg_id
    
    def get_context(self, project_id: Optional[str], chat_id: str, current_prompt: str, max_memories: int = 10) -> str:
        """
        Retrieve context from current chat and project memories.
        Returns a formatted context string to prepend to the prompt.
        """
        context_parts = []
        
        # 1. Current chat history (last 10 messages)
        chat_history = self._get_chat_history(chat_id, limit=10)
        if chat_history:
            context_parts.append("# Current Chat History")
            for msg in chat_history:
                role = "User" if msg["role"] == "user" else "Assistant"
                context_parts.append(f"{role}: {msg['content']}")
        
        # 2. Project memories (relevant to current prompt)
        if project_id:
            relevant = self._retrieve_relevant_memories(project_id, current_prompt, limit=5)
            if relevant:
                context_parts.append("\n# Relevant Past Memories")
                for mem in relevant:
                    context_parts.append(f"- {mem['content']} (from {mem['chat_id']})")
        
        # 3. Knowledge base (if any)
        # Could be added here
        
        return "\n".join(context_parts)
    
    def _get_chat_history(self, chat_id: str, limit: int = 50) -> List[Dict]:
        """Retrieve recent chat history."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, created_at
                FROM memory_messages
                WHERE chat_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (chat_id, limit))
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]
    
    def _retrieve_relevant_memories(self, project_id: str, query: str, limit: int = 5) -> List[Dict]:
        """
        Retrieve semantically relevant memories from the project.
        Uses vector similarity if available; falls back to keyword search.
        """
        try:
            # Attempt vector search (if embeddings available)
            results = self.vector_store.search(project_id, query, limit)
            return results
        except Exception as e:
            logger.warning(f"Vector search failed, using keyword fallback: {e}")
            # Keyword fallback
            with get_db_connection() as conn:
                cursor = conn.cursor()
                search_pattern = f"%{query}%"
                cursor.execute("""
                    SELECT id, chat_id, role, content, created_at
                    FROM memory_messages
                    WHERE project_id = ? AND content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (project_id, search_pattern, limit))
                rows = cursor.fetchall()
                return [{"id": r[0], "chat_id": r[1], "role": r[2], "content": r[3], "timestamp": r[4]} for r in rows]
    
    def get_project_memory(self, project_id: str, limit: int = 1000) -> List[Dict]:
        """Get all messages from a project (for the 'immortal notebook' feature)."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.chat_id, m.role, m.content, m.created_at, c.title as chat_title
                FROM memory_messages m
                LEFT JOIN chat_sessions c ON m.chat_id = c.id
                WHERE m.project_id = ?
                ORDER BY m.created_at DESC
                LIMIT ?
            """, (project_id, limit))
            rows = cursor.fetchall()
            return [{"id": r[0], "chat_id": r[1], "role": r[2], "content": r[3], "timestamp": r[4], "chat_title": r[5]} for r in rows]
    
    def add_to_knowledge(self, project_id: str, title: str, content: str, source: Optional[str] = None) -> str:
        """Add a document to the knowledge base."""
        entry_id = str(uuid.uuid4())[:8]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge_entries (id, project_id, title, content, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (entry_id, project_id, title, content, source, datetime.utcnow().isoformat()))
            conn.commit()
        logger.info(f"Added knowledge entry {entry_id} to project {project_id}")
        return entry_id
