# tests/test_memory.py
"""
Memory module tests.
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.memory.memory_integration import MemoryManager
from src.database.connection import get_db_connection


@pytest.fixture
def memory_manager():
    """Create a MemoryManager with a test database."""
    # Use in-memory SQLite for testing
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    mm = MemoryManager()
    yield mm
    # Cleanup
    if original_url:
        os.environ["DATABASE_URL"] = original_url


def test_create_chat(memory_manager):
    chat_id = memory_manager.create_chat(project_id="test_project", title="Test Chat")
    assert chat_id is not None
    assert len(chat_id) == 8


def test_save_message(memory_manager):
    chat_id = memory_manager.create_chat()
    msg_id = memory_manager.save_message(chat_id, "user", "Hello, world!")
    assert msg_id is not None
    # Verify it was saved
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM memory_messages WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Hello, world!"


def test_get_context(memory_manager):
    chat_id = memory_manager.create_chat()
    memory_manager.save_message(chat_id, "user", "What is AI?")
    memory_manager.save_message(chat_id, "assistant", "AI is artificial intelligence.")
    context = memory_manager.get_context(None, chat_id, "Tell me more about AI.")
    assert "AI is artificial intelligence" in context


def test_project_memory_retrieval(memory_manager):
    project_id = "test_project"
    chat1 = memory_manager.create_chat(project_id)
    chat2 = memory_manager.create_chat(project_id)
    
    memory_manager.save_message(chat1, "user", "Message in chat 1")
    memory_manager.save_message(chat2, "user", "Message in chat 2")
    
    # Retrieve all project memory
    all_memories = memory_manager.get_project_memory(project_id)
    assert len(all_memories) >= 2
    # Should contain both messages
    contents = [m["content"] for m in all_memories]
    assert "Message in chat 1" in contents
    assert "Message in chat 2" in contents
