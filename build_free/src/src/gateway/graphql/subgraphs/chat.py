# gateway/graphql/subgraphs/chat.py – Chat subgraph (Federated)
import strawberry
from strawberry.federation import FederationField
from typing import List, Optional

@strawberry.federation.type(keys=["id"])
class Conversation:
    id: strawberry.ID
    user_id: str
    messages: List[str]

@strawberry.federation.type(extend=True, keys=["id"])
class User:
    id: strawberry.ID

    @strawberry.federation.field
    def conversations(self) -> List[Conversation]:
        # Resolve via chat service
        return []

@strawberry.type
class Query:
    @strawberry.field
    def conversation(self, id: strawberry.ID) -> Optional[Conversation]:
        return Conversation(id=id, user_id="user-1", messages=["Hello"])

    @strawberry.field
    def conversations_by_user(self, user_id: strawberry.ID) -> List[Conversation]:
        return []

schema = strawberry.federation.Schema(query=Query)
