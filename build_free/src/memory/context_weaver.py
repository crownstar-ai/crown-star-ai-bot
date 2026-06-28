# src/memory/context_weaver.py
from .immortal_notebook import ImmortalNotebook
from .project_manager import ProjectManager
from typing import List, Dict

class ContextWeaver:
    def __init__(self):
        self.notebook = ImmortalNotebook()
        self.project_manager = ProjectManager()

    def weave_context(self, project_id: str, current_message: str, max_memories: int = 10) -> str:
        all_memories = self.notebook.get_project_memory(project_id, limit=1000)
        scored_memories = []
        for mem in all_memories:
            score = self._relevance_score(current_message, mem["content"])
            scored_memories.append((score, mem))
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_memories = scored_memories[:max_memories]

        if not top_memories:
            return ""

        context = "\n\n# Previous Relevant Conversations (for context):\n"
        for score, mem in top_memories:
            role_icon = "User" if mem["role"] == "user" else "Assistant"
            context += f"\n## {role_icon} (chat: {mem.get('chat_id', 'unknown')[:6]}):\n{mem['content'][:500]}\n"
        context += "\n# Current Conversation:\n"
        return context

    def _relevance_score(self, current: str, past: str) -> float:
        current_words = set(current.lower().split())
        past_words = set(past.lower().split())
        overlap = len(current_words & past_words)
        return overlap / (len(current_words) + 0.1)

    def get_full_context(self, project_id: str, chat_id: str, current_message: str) -> str:
        chat_history = self.notebook.get_chat_history(chat_id, limit=50)
        chat_context = "\n".join([f"{m['role']}: {m['content']}" for m in chat_history])
        memory_context = self.weave_context(project_id, current_message, max_memories=8)
        return memory_context + chat_context
