# gateway/graphql/subgraphs/users.py – Users subgraph
import strawberry
from typing import List, Optional

@strawberry.federation.type(keys=["id"])
class User:
    id: strawberry.ID
    name: str
    email: str

@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: strawberry.ID) -> Optional[User]:
        return User(id=id, name="Demo User", email="demo@crownstar.ai")
    
    @strawberry.field
    def users(self) -> List[User]:
        return []

schema = strawberry.federation.Schema(query=Query)
