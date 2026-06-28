# optimization/api.py – REST endpoints for optimization
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import numpy as np
from .sa.engine import SimulatedAnnealing, AnnealingSchedule, rosenbrock, sphere
from .ga.engine import GeneticAlgorithm, GAParameters
from .qubo.solver import QUBOSolver, QUBOProblem, create_random_qubo
from .core_integration import CrownStarOptimizer
from security.dependencies import require_permission

router = APIRouter(prefix="/v1/optimize", tags=["Optimization"])

class SARequest(BaseModel):
    function: str  # "rosenbrock", "sphere", or custom expression (not implemented)
    dim: int = 2
    bounds: List[List[float]] = None
    initial_temp: float = 100.0
    cooling_rate: float = 0.99
    max_iters: int = 1000

class GARequest(BaseModel):
    function: str
    dim: int = 2
    bounds: List[List[float]] = None
    population_size: int = 100
    generations: int = 200
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1

class QUBORequest(BaseModel):
    n: int = 5
    method: str = "sa"  # bruteforce, greedy, sa
    random_seed: Optional[int] = None

class PromptTuneRequest(BaseModel):
    method: str = "sa"

@router.post("/sa")
async def simulated_annealing_opt(req: SARequest, user: dict = Depends(require_permission("user"))):
    if req.function == "rosenbrock":
        objective = rosenbrock
    elif req.function == "sphere":
        objective = sphere
    else:
        raise HTTPException(400, "Unsupported function")
    if req.bounds is None:
        bounds = np.array([[-5.0, 5.0]] * req.dim)
    else:
        bounds = np.array(req.bounds)
    schedule = AnnealingSchedule(initial_temp=req.initial_temp, cooling_rate=req.cooling_rate, max_iterations=req.max_iters)
    sa = SimulatedAnnealing(objective, bounds, schedule)
    best_x, best_val = sa.optimize()
    return {"best_params": best_x.tolist(), "best_value": best_val, "history": sa.history[-10:]}

@router.post("/ga")
async def genetic_algorithm_opt(req: GARequest, user: dict = Depends(require_permission("user"))):
    if req.function == "rosenbrock":
        objective = rosenbrock
    elif req.function == "sphere":
        objective = sphere
    else:
        raise HTTPException(400, "Unsupported function")
    if req.bounds is None:
        bounds = np.array([[-5.0, 5.0]] * req.dim)
    else:
        bounds = np.array(req.bounds)
    params = GAParameters(
        population_size=req.population_size,
        generations=req.generations,
        crossover_rate=req.crossover_rate,
        mutation_rate=req.mutation_rate
    )
    ga = GeneticAlgorithm(objective, bounds, params)
    best_x, best_val = ga.optimize()
    return {"best_params": best_x.tolist(), "best_value": best_val, "history": ga.history[-10:]}

@router.post("/qubo")
async def qubo_opt(req: QUBORequest, user: dict = Depends(require_permission("user"))):
    problem = create_random_qubo(req.n, seed=req.random_seed)
    solver = QUBOSolver(problem)
    if req.method == "bruteforce":
        if problem.n > 20:
            raise HTTPException(400, "Brute‑force only for n <= 20")
        x, val = solver.brute_force()
    elif req.method == "greedy":
        x, val = solver.greedy()
    else:
        x, val = solver.simulated_annealing()
    return {"solution": x.tolist(), "value": val, "Q": problem.Q.tolist()}

@router.post("/prompt_tune")
async def tune_prompt_parameters(req: PromptTuneRequest, user: dict = Depends(require_permission("pro"))):
    optimizer = CrownStarOptimizer()
    result = optimizer.optimize_prompt_parameters(method=req.method)
    return result
