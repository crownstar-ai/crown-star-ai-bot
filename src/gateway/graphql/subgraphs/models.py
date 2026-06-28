# gateway/graphql/subgraphs/models.py – Models subgraph
import strawberry
from typing import List, Optional

@strawberry.federation.type(keys=["name"])
class Model:
    name: str
    provider: str
    context_length: int

@strawberry.type
class Query:
    @strawberry.field
    def model(self, name: str) -> Optional[Model]:
        return Model(name=name, provider="DeepSeek", context_length=8192)
    
    @strawberry.field
    def models(self) -> List[Model]:
        return [Model(name="deepseek_v2_lite", provider="DeepSeek", context_length=4096),
                Model(name="gpt4", provider="OpenAI", context_length=8192)]

schema = strawberry.federation.Schema(query=Query)
