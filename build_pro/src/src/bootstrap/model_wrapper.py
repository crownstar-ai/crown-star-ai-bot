# src/bootstrap/model_wrapper.py
from typing import Dict, List, Optional, Callable
from memory.immortal_notebook import ImmortalNotebook
from memory.context_weaver import ContextWeaver
from memory.project_manager import ProjectManager

class CrownStarBootstrap:
    def __init__(self, model_adapter: Callable):
        self.model_adapter = model_adapter
        self.notebook = ImmortalNotebook()
        self.weaver = ContextWeaver()
        self.project_manager = ProjectManager()

    def chat(self,
             prompt: str,
             project_id: str,
             chat_id: str = None,
             temperature: float = 0.7,
             max_tokens: int = 2048,
             modules_active: List[str] = None,
             **kwargs) -> Dict:
        if not chat_id:
            chat_id = self.notebook.create_chat(project_id, title=prompt[:50])

        self.notebook.add_message(chat_id, "user", prompt, {"project_id": project_id})

        full_prompt = self.weaver.get_full_context(project_id, chat_id, prompt)
        full_prompt += f"\nUser: {prompt}\nAssistant:"

        response = self.model_adapter(
            prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        self.notebook.add_message(chat_id, "assistant", response, {"project_id": project_id})

        return {
            "response": response,
            "chat_id": chat_id,
            "project_id": project_id,
            "memory_count": len(self.notebook.get_project_memory(project_id, limit=10000))
        }

    def switch_model(self, new_adapter: Callable):
        self.model_adapter = new_adapter

    def get_project_memory(self, project_id: str) -> List[Dict]:
        return self.notebook.get_project_memory(project_id)
