# src/memory/project_manager.py
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

class ProjectManager:
    def __init__(self, data_dir: str = "data/projects"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, description: str = "") -> Dict:
        project_id = str(uuid.uuid4())[:8]
        project = {
            "id": project_id,
            "name": name,
            "description": description,
            "created_at": datetime.utcnow().isoformat(),
            "chat_ids": []
        }
        self._save_project(project)
        return project

    def get_project(self, project_id: str) -> Optional[Dict]:
        path = self.data_dir / f"{project_id}.json"
        if not path.exists():
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_projects(self) -> List[Dict]:
        projects = []
        for path in self.data_dir.glob("*.json"):
            with open(path, 'r', encoding='utf-8') as f:
                projects.append(json.load(f))
        return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

    def add_chat_to_project(self, project_id: str, chat_id: str) -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        if chat_id not in project["chat_ids"]:
            project["chat_ids"].append(chat_id)
            self._save_project(project)
        return True

    def _save_project(self, project: Dict):
        path = self.data_dir / f"{project['id']}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(project, f, indent=2)
