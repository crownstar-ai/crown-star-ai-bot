# finetune/data/dataset_utils.py – Convert CrownStar data to training format
import json
import sqlite3
import csv
from pathlib import Path
from typing import List, Dict

class ConversationDatasetBuilder:
    @staticmethod
    def from_conversations(db_path: str = "data/conversations/crownstar_memory.db", output_path: str = "data/finetune/datasets/conversations.jsonl"):
        """Extract conversations from CrownStar memory DB to instruction format"""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT user_message, assistant_message FROM conversations ORDER BY id ASC")
        rows = cursor.fetchall()
        with open(output_path, "w") as f:
            for user_msg, assistant_msg in rows:
                text = f"User: {user_msg}\nAssistant: {assistant_msg}"
                json.dump({"text": text}, f)
                f.write("\n")
        conn.close()
        print(f"Exported {len(rows)} conversations to {output_path}")
        return output_path
    
    @staticmethod
    def from_jsonl(input_path: str, output_path: str = None, instruction_field: str = "text"):
        """Normalize JSONL to training format"""
        data = []
        with open(input_path, "r") as f:
            for line in f:
                item = json.loads(line)
                if instruction_field in item:
                    data.append({"text": item[instruction_field]})
                elif "messages" in item:
                    # ChatML format
                    text = "\n".join([f"{m['role']}: {m['content']}" for m in item["messages"]])
                    data.append({"text": text})
        output = output_path or input_path.replace(".jsonl", "_formatted.jsonl")
        with open(output, "w") as f:
            for item in data:
                json.dump(item, f)
                f.write("\n")
        return output

def create_dataset_from_conversations(limit: int = 1000):
    builder = ConversationDatasetBuilder()
    return builder.from_conversations()
