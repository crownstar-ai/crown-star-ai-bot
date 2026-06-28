# serverless/azure/__init__.py – Azure Functions HTTP trigger
import azure.functions as func
import logging
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from crownstar_core import create_core

core = None

def main(req: func.HttpRequest) -> func.HttpResponse:
    global core
    if core is None:
        core = create_core()
        logging.info("CrownStar core initialized")
    
    try:
        req_body = req.get_json()
        query = req_body.get("query", "")
        modules = req_body.get("modules", {})
        tier = req_body.get("tier", None)
        
        for mod, enabled in modules.items():
            core.set_module(mod, enabled)
        if tier:
            core.set_tier(tier)
        
        result = core.answer(query)
        return func.HttpResponse(
            json.dumps({
                "answer": result["answer"],
                "conversation_id": result["conversation_id"],
                "latency_ms": result["latency_ms"]
            }),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)
