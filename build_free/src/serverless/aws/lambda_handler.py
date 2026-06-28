# serverless/aws/lambda_handler.py – AWS Lambda handler for CrownStar API
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
from fastapi import FastAPI
from mangum import Mangum
from crownstar_core import create_core
from api.crownstar_enterprise_api import app as enterprise_app
from logging.structured_logger import setup_json_logging

# Setup logging for Lambda (stdout)
setup_json_logging()

# Initialize core (cold start optimisation)
core = create_core()

# FastAPI app (reuse existing enterprise app if available, otherwise create minimal)
app = enterprise_app

# Wrap with Mangum for API Gateway integration
handler = Mangum(app, lifespan="off")

# Optional: warmup handler for Lambda reserved concurrency
def warmup_handler(event, context):
    return {"statusCode": 200, "body": "warmed"}

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
