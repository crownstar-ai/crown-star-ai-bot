# gateway/graphql/subgraphs/analytics.py – Analytics subgraph
import strawberry
from typing import List

@strawberry.type
class UsageMetric:
    date: str
    requests: int
    cost: float

@strawberry.type
class Query:
    @strawberry.field
    def usage(self, start_date: str, end_date: str) -> List[UsageMetric]:
        return []

schema = strawberry.federation.Schema(query=Query)
