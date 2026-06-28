# nlp/api.py – FastAPI endpoints for NLP features
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from .service import nlp

router = APIRouter(prefix="/v1/nlp", tags=["NLP"])

class SummarizeRequest(BaseModel):
    text: str
    max_length: Optional[int] = 150
    min_length: Optional[int] = 30

class SentimentRequest(BaseModel):
    text: str

class EmbedRequest(BaseModel):
    text: str

class ClassifyRequest(BaseModel):
    text: str
    labels: List[str]

class BatchSummarizeRequest(BaseModel):
    texts: List[str]
    max_length: Optional[int] = 150

@router.post("/summarize")
async def summarize_endpoint(req: SummarizeRequest):
    result = await nlp.summarize(req.text, req.max_length, req.min_length)
    return {"summary": result, "original_length": len(req.text), "summary_length": len(result)}

@router.post("/sentiment")
async def sentiment_endpoint(req: SentimentRequest):
    result = await nlp.analyze_sentiment(req.text)
    return result

@router.post("/embed")
async def embed_endpoint(req: EmbedRequest):
    embedding = await nlp.get_embedding(req.text)
    return {"embedding": embedding[:10], "dimensions": len(embedding)}  # return first 10 for brevity

@router.post("/classify")
async def classify_endpoint(req: ClassifyRequest):
    result = await nlp.classify(req.text, req.labels)
    return result

@router.post("/batch/summarize")
async def batch_summarize(req: BatchSummarizeRequest):
    results = await nlp.batch_summarize(req.texts, req.max_length)
    return {"summaries": results}

@router.post("/batch/sentiment")
async def batch_sentiment(req: BatchSummarizeRequest):
    results = await nlp.batch_sentiment(req.texts)
    return {"results": results}
