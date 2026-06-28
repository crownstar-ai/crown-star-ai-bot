# automl/api.py – REST API for AutoML
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from .core import get_automl_manager, SearchSpace, OptimisationAlgorithm
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/automl", tags=["AutoML"])

class OptimisationRequest(BaseModel):
    task_name: str
    search_space: List[Dict]
    algorithm: str = "bayesian"
    total_trials: int = 50

@router.post("/optimise")
async def start_optimisation(req: OptimisationRequest, background_tasks: BackgroundTasks, user=Depends(require_permission("admin"))):
    mgr = get_automl_manager()
    def dummy_train(params, max_epochs):
        import time, random
        time.sleep(random.uniform(0.5, 2))
        accuracy = 0.5 + random.random() * 0.4
        return accuracy, {"loss": 1.0 - accuracy}
    opt_id = mgr.start_optimisation(
        task_name=req.task_name,
        search_space=req.search_space,
        algorithm=req.algorithm,
        total_trials=req.total_trials,
        train_func=dummy_train
    )
    return {"optimisation_id": opt_id, "status": "started"}

@router.get("/status/{opt_id}")
async def get_status(opt_id: str, user=Depends(require_permission("admin"))):
    mgr = get_automl_manager()
    status = mgr.get_status(opt_id)
    if "error" in status:
        raise HTTPException(404, status["error"])
    return status

@router.get("/trials/{opt_id}")
async def list_trials(opt_id: str, user=Depends(require_permission("admin"))):
    mgr = get_automl_manager()
    trials = mgr.get_trials(opt_id)
    return {"trials": [asdict(t) for t in trials]}

@router.get("/best/{opt_id}")
async def get_best_trial(opt_id: str, user=Depends(require_permission("admin"))):
    mgr = get_automl_manager()
    best = mgr.get_best_trial(opt_id)
    if not best:
        raise HTTPException(404, "No completed trials found")
    return asdict(best)
