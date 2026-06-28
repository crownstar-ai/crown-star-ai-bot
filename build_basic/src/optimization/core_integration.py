# optimization/core_integration.py – Use optimization to tune CrownStar parameters
import numpy as np
from optimization.sa.engine import SimulatedAnnealing, AnnealingSchedule
from optimization.ga.engine import GeneticAlgorithm, GAParameters
from optimization.qubo.solver import QUBOSolver, QUBOProblem, create_random_qubo
from crownstar_core import create_core

class CrownStarOptimizer:
    def __init__(self, core=None):
        self.core = core or create_core()
    
    def objective_prompt_engineering(self, params: np.ndarray) -> float:
        """Optimize temperature, top_p, max_tokens, etc. for quality"""
        # params: [temperature, top_p, max_tokens, repetition_penalty]
        temperature = float(np.clip(params[0], 0.1, 2.0))
        top_p = float(np.clip(params[1], 0.5, 1.0))
        max_tokens = int(np.clip(params[2], 50, 2000))
        # In real implementation, evaluate on benchmark queries
        # For simulation, return random score (lower is better)
        score = -temperature * top_p + 0.001 * max_tokens + np.random.randn() * 0.1
        return score
    
    def optimize_prompt_parameters(self, method: str = "sa") -> dict:
        bounds = np.array([[0.1, 2.0], [0.5, 1.0], [50, 2000], [0.9, 1.2]])
        if method == "sa":
            sa = SimulatedAnnealing(self.objective_prompt_engineering, bounds)
            best_params, best_value = sa.optimize()
        elif method == "ga":
            ga = GeneticAlgorithm(self.objective_prompt_engineering, bounds)
            best_params, best_value = ga.optimize()
        else:
            raise ValueError("Method must be 'sa' or 'ga'")
        return {
            "temperature": best_params[0],
            "top_p": best_params[1],
            "max_tokens": int(best_params[2]),
            "repetition_penalty": best_params[3],
            "objective_value": best_value
        }
    
    def solve_qubo(self, Q: np.ndarray, method: str = "sa") -> dict:
        problem = QUBOProblem(Q, Q.shape[0])
        solver = QUBOSolver(problem)
        if method == "bruteforce" and problem.n <= 20:
            x, val = solver.brute_force()
        elif method == "greedy":
            x, val = solver.greedy()
        else:
            x, val = solver.simulated_annealing()
        return {"solution": x.tolist(), "value": val}
