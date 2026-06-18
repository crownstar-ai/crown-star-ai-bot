import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import openai

app = FastAPI(title="CrownStar AI Bot")

@app.get("/")
def root():
    return {"message": "CrownStar AI Bot is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/chat")
def chat(prompt: str):
    # Placeholder: you'll replace with real DeepSeek logic
    return {"response": f"Echo: {prompt}"}
