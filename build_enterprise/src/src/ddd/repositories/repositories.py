# ddd/repositories/repositories.py – Repository pattern for aggregates
from abc import ABC, abstractmethod
from typing import Optional, List
import sqlite3
import json
from pathlib import Path
from ..entities.domain_entities import Conversation, User, ModuleConfiguration
from ..value_object import ConversationId, UserId, Tier, ModelName, Money

class ConversationRepository(ABC):
    @abstractmethod
    def save(self, conversation: Conversation) -> None:
        pass
    @abstractmethod
    def find_by_id(self, conversation_id: ConversationId) -> Optional[Conversation]:
        pass
    @abstractmethod
    def find_by_user(self, user_id: UserId, limit: int = 50) -> List[Conversation]:
        pass
    @abstractmethod
    def delete(self, conversation_id: ConversationId) -> bool:
        pass

class UserRepository(ABC):
    @abstractmethod
    def save(self, user: User) -> None:
        pass
    @abstractmethod
    def find_by_id(self, user_id: UserId) -> Optional[User]:
        pass
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[User]:
        pass
    @abstractmethod
    def list_all(self, limit: int = 100) -> List[User]:
        pass

class ModuleConfigurationRepository(ABC):
    @abstractmethod
    def get(self) -> ModuleConfiguration:
        pass
    @abstractmethod
    def save(self, config: ModuleConfiguration) -> None:
        pass

# SQLite implementation
class SQLiteConversationRepository(ConversationRepository):
    def __init__(self, db_path: str = "data/ddd/conversations.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_table()
    def _init_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                tier TEXT,
                messages TEXT,
                created_at TEXT,
                updated_at TEXT,
                version INTEGER
            )
        ''')
        self.conn.commit()
    def save(self, conversation: Conversation) -> None:
        self.conn.execute('''
            INSERT OR REPLACE INTO conversations (id, user_id, tier, messages, created_at, updated_at, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            conversation.id.value,
            conversation.user_id.value,
            conversation.tier.name,
            json.dumps(conversation.messages),
            conversation.created_at.isoformat(),
            conversation.updated_at.isoformat(),
            conversation.version
        ))
        self.conn.commit()
    def find_by_id(self, conversation_id: ConversationId) -> Optional[Conversation]:
        cur = self.conn.execute("SELECT id, user_id, tier, messages, created_at, updated_at, version FROM conversations WHERE id = ?", (conversation_id.value,))
        row = cur.fetchone()
        if not row:
            return None
        from ..value_object import ConversationId, UserId, Tier
        import json, datetime
        return Conversation(
            id=ConversationId(row[0]),
            user_id=UserId(row[1]),
            tier=Tier(row[2]),
            messages=json.loads(row[3]),
            created_at=datetime.datetime.fromisoformat(row[4]),
            updated_at=datetime.datetime.fromisoformat(row[5]),
            version=row[6]
        )
    def find_by_user(self, user_id: UserId, limit: int = 50) -> List[Conversation]:
        cur = self.conn.execute("SELECT id, user_id, tier, messages, created_at, updated_at, version FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?", (user_id.value, limit))
        rows = cur.fetchall()
        import json, datetime
        result = []
        for row in rows:
            result.append(Conversation(
                id=ConversationId(row[0]),
                user_id=UserId(row[1]),
                tier=Tier(row[2]),
                messages=json.loads(row[3]),
                created_at=datetime.datetime.fromisoformat(row[4]),
                updated_at=datetime.datetime.fromisoformat(row[5]),
                version=row[6]
            ))
        return result
    def delete(self, conversation_id: ConversationId) -> bool:
        cur = self.conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id.value,))
        self.conn.commit()
        return cur.rowcount > 0

class SQLiteUserRepository(UserRepository):
    def __init__(self, db_path: str = "data/ddd/users.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_table()
    def _init_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                email TEXT,
                tier TEXT,
                current_model TEXT,
                modules TEXT,
                created_at TEXT,
                last_active TEXT,
                total_requests INTEGER,
                total_cost_amount REAL,
                version INTEGER
            )
        ''')
        self.conn.commit()
    def save(self, user: User) -> None:
        self.conn.execute('''
            INSERT OR REPLACE INTO users (id, username, email, tier, current_model, modules, created_at, last_active, total_requests, total_cost_amount, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user.id.value,
            user.username,
            user.email,
            user.tier.name,
            user.current_model.value,
            json.dumps(user.modules),
            user.created_at.isoformat(),
            user.last_active.isoformat(),
            user.total_requests,
            user.total_cost.amount,
            user.version
        ))
        self.conn.commit()
    def find_by_id(self, user_id: UserId) -> Optional[User]:
        cur = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id.value,))
        row = cur.fetchone()
        if not row:
            return None
        import json, datetime
        return User(
            id=UserId(row[0]),
            username=row[1],
            email=row[2],
            tier=Tier(row[3]),
            current_model=ModelName(row[4]),
            modules=json.loads(row[5]),
            created_at=datetime.datetime.fromisoformat(row[6]),
            last_active=datetime.datetime.fromisoformat(row[7]),
            total_requests=row[8],
            total_cost=Money(row[9]),
            version=row[10]
        )
    def find_by_username(self, username: str) -> Optional[User]:
        cur = self.conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_user(row)
    def list_all(self, limit: int = 100) -> List[User]:
        cur = self.conn.execute("SELECT * FROM users LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [self._row_to_user(row) for row in rows]
    def _row_to_user(self, row):
        import json, datetime
        return User(
            id=UserId(row[0]),
            username=row[1],
            email=row[2],
            tier=Tier(row[3]),
            current_model=ModelName(row[4]),
            modules=json.loads(row[5]),
            created_at=datetime.datetime.fromisoformat(row[6]),
            last_active=datetime.datetime.fromisoformat(row[7]),
            total_requests=row[8],
            total_cost=Money(row[9]),
            version=row[10]
        )

class SQLiteModuleConfigurationRepository(ModuleConfigurationRepository):
    def __init__(self, db_path: str = "data/ddd/config.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_table()
    def _init_table(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id TEXT PRIMARY KEY,
                modules TEXT,
                version INTEGER,
                updated_at TEXT
            )
        ''')
        self.conn.commit()
    def get(self) -> ModuleConfiguration:
        cur = self.conn.execute("SELECT modules, version, updated_at FROM config WHERE id = 'global_config'")
        row = cur.fetchone()
        if not row:
            return ModuleConfiguration()
        import json, datetime
        config = ModuleConfiguration()
        config.modules = json.loads(row[0])
        config.version = row[1]
        config.updated_at = datetime.datetime.fromisoformat(row[2])
        return config
    def save(self, config: ModuleConfiguration) -> None:
        self.conn.execute('''
            INSERT OR REPLACE INTO config (id, modules, version, updated_at)
            VALUES (?, ?, ?, ?)
        ''', ('global_config', json.dumps(config.modules), config.version, config.updated_at.isoformat()))
        self.conn.commit()
