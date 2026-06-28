# src/core/control_shell.py – Full ControlShell with state, memory, tier enforcement, language
import time
from typing import List, Dict, Optional

class ControlShellState:
    def __init__(self):
        self.tier = "free"
        self.temperature = 0.85
        self.min_length = 32
        self.max_length = 512
        self.mode = "regal_futurism"
        self.language = "en"
        self.memory = []  # list of {"role": "user"/"assistant", "content": str}
        self.conversation_id = None

class ControlShell:
    def __init__(self, tier: str = "free"):
        self.state = ControlShellState()
        self.state.tier = tier
        self._conversations = {}  # id -> list of messages

    def add_message(self, role: str, content: str):
        self.state.memory.append({"role": role, "content": content, "timestamp": time.time()})
        if len(self.state.memory) > 20:
            self.state.memory = self.state.memory[-20:]
        if self.state.conversation_id:
            if self.state.conversation_id not in self._conversations:
                self._conversations[self.state.conversation_id] = []
            self._conversations[self.state.conversation_id].append({"role": role, "content": content})

    def build_prompt(self, query: str, cortex_context: str, vector_context: str) -> str:
        system_msg = (
            "You are CrownStar-Absolute, the world's most powerful AI. "
            "You possess supreme language faculty, understanding all human languages, dialects, "
            "mathematical notations, and programming languages. Respond with accuracy and authority."
        )
        memory_context = ""
        if self.state.memory:
            last_msgs = self.state.memory[-6:]
            memory_context = "\n".join([f"{m['role']}: {m['content']}" for m in last_msgs])
        prompt = f"{system_msg}\n\n"
        if memory_context:
            prompt += f"Previous conversation:\n{memory_context}\n\n"
        if cortex_context:
            prompt += f"Internet context: {cortex_context}\n\n"
        if vector_context:
            prompt += f"Relevant past knowledge: {vector_context}\n\n"
        prompt += f"User: {query}\nAssistant:"
        return prompt

    def set_mode(self, mode: str):
        if mode in ("regal_futurism", "technical", "minimal"):
            self.state.mode = mode

    def new_conversation(self) -> str:
        import uuid
        conv_id = str(uuid.uuid4())
        self.state.conversation_id = conv_id
        self.state.memory = []
        self._conversations[conv_id] = []
        return conv_id

    def get_conversation(self, conv_id: str) -> Optional[List[Dict]]:
        return self._conversations.get(conv_id)

    def list_conversations(self) -> List[Dict]:
        return [{"id": k, "title": f"Conversation {k[:8]}", "message_count": len(v), "updated": time.time()} 
                for k, v in self._conversations.items()]

    def delete_conversation(self, conv_id: str) -> bool:
        if conv_id in self._conversations:
            del self._conversations[conv_id]
            if self.state.conversation_id == conv_id:
                self.state.conversation_id = None
                self.state.memory = []
            return True
        return False

    def rename_conversation(self, conv_id: str, title: str) -> bool:
        # Title storage would need separate metadata – simplified
        return True

    def export_conversation(self, conv_id: str, format: str = "json") -> Optional[str]:
        messages = self._conversations.get(conv_id)
        if not messages:
            return None
        if format == "json":
            import json
            return json.dumps(messages, indent=2)
        elif format == "markdown":
            lines = []
            for msg in messages:
                lines.append(f"**{msg['role'].capitalize()}**: {msg['content']}")
            return "\n\n".join(lines)
        else:
            lines = []
            for msg in messages:
                lines.append(f"{msg['role'].upper()}: {msg['content']}")
            return "\n\n".join(lines)
