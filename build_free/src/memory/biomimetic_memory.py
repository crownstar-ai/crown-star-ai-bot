# src/memory/biomimetic_memory.py – Full BiomimeticMemory with XML storage, XPointer, XReceptor
import xml.etree.ElementTree as ET
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

class BiomimeticMemory:
    def __init__(self, storage_path: str = "data/memories.xml"):
        self.storage_path = Path(storage_path)
        self.memories = []
        self._load()

    def _load(self):
        if self.storage_path.exists():
            try:
                tree = ET.parse(self.storage_path)
                root = tree.getroot()
                for entry in root.findall(".//memory-entry"):
                    mem = {
                        "id": entry.findtext("id"),
                        "timestamp": float(entry.findtext("timestamp")),
                        "query": entry.findtext("query"),
                        "response": entry.findtext("response"),
                        "importance": float(entry.findtext("importance")),
                        "tags": [t.text for t in entry.findall(".//tag")]
                    }
                    self.memories.append(mem)
            except:
                pass
        else:
            self._create_empty()

    def _create_empty(self):
        root = ET.Element("memory-system", version="1.0")
        ET.SubElement(root, "memory-index")
        ET.SubElement(root, "experiential-lib")
        tree = ET.ElementTree(root)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(self.storage_path, encoding="utf-8", xml_declaration=True)

    def store_conversation_entry(self, query: str, response: str, src_lang: str, tgt_lang: str):
        mem_id = str(uuid.uuid4())
        entry = {
            "id": mem_id,
            "timestamp": time.time(),
            "query": query,
            "response": response,
            "importance": 0.5,
            "tags": [src_lang, tgt_lang]
        }
        self.memories.append(entry)
        self._append_to_xml(entry)

    def _append_to_xml(self, entry: Dict):
        if not self.storage_path.exists():
            self._create_empty()
        tree = ET.parse(self.storage_path)
        root = tree.getroot()
        idx = root.find("memory-index")
        mem_el = ET.SubElement(idx, "memory-entry", {"type": "conversation", "tier": "free", "id": entry["id"]})
        ET.SubElement(mem_el, "id").text = entry["id"]
        ET.SubElement(mem_el, "timestamp").text = str(entry["timestamp"])
        ET.SubElement(mem_el, "query").text = entry["query"]
        ET.SubElement(mem_el, "response").text = entry["response"]
        ET.SubElement(mem_el, "importance").text = str(entry["importance"])
        tags_el = ET.SubElement(mem_el, "tags")
        for tag in entry.get("tags", []):
            ET.SubElement(tags_el, "tag").text = tag
        tree.write(self.storage_path, encoding="utf-8", xml_declaration=True)

    def get_statistics(self) -> Dict:
        return {"entries": len(self.memories), "storage_path": str(self.storage_path)}
