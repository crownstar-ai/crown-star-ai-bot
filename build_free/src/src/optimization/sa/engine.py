# optimization/sa/engine.py – Simulated Annealing for general optimization
import math
import random
import numpy as np
from typing import Callable, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import time

@dataclass
class AnnealingSchedule:
    initial_temp: float = 100.0
    cooling_rate: float = 0.99
    min_temp: float = 1e-8
    max_iterations: int = 1000
    temperature_function: str = "geometric"  # geometric, linear, logarithmic

class SimulatedAnnealing:
    def __init__(self, objective: Callable[[np.ndarray], float], bounds: np.ndarray, schedule: AnnealingSchedule = None):
        """
        objective: function mapping parameter vector to cost (lower is better)
        bounds: n x 2 array [[min1, max1], [min2, max2], ...]
        """
        self.objective = objective
        self.bounds = bounds
        self.dim = bounds.shape[0]
        self.schedule = schedule or AnnealingSchedule()
        self.history = []  # track best value per iteration
    
    def _neighbor(self, x: np.ndarray, step_scale: float = 0.1) -> np.ndarray:
        """Generate neighbor by Gaussian perturbation within bounds"""
        step = step_scale * (self.bounds[:,1] - self.bounds[:,0]) * np.random.randn(self.dim)
        x_new = x + step
        # Clip to bounds
        x_new = np.clip(x_new, self.bounds[:,0], self.bounds[:,1])
        return x_new
    
    def _temperature(self, t: float, iteration: int) -> float:
        if self.schedule.temperature_function == "geometric":
            return t * self.schedule.cooling_rate
        elif self.schedule.temperature_function == "linear":
            return t * (1 - iteration / self.schedule.max_iterations)
        elif self.schedule.temperature_function == "logarithmic":
            return t / (1 + math.log(1 + iteration))
        else:
            return t * self.schedule.cooling_rate
    
    def optimize(self, initial_x: Optional[np.ndarray] = None, verbose: bool = False) -> Tuple[np.ndarray, float]:
        if initial_x is None:
            x = np.random.uniform(self.bounds[:,0], self.bounds[:,1])
        else:
            x = np.clip(initial_x, self.bounds[:,0], self.bounds[:,1])
        current_val = self.objective(x)
        best_x = x.copy()
        best_val = current_val
        temp = self.schedule.initial_temp
        self.history = [best_val]
        
        for iteration in range(self.schedule.max_iterations):
            x_new = self._neighbor(x, step_scale=0.1 * (1 - iteration/self.schedule.max_iterations))
            new_val = self.objective(x_new)
            delta = new_val - current_val
            if delta < 0 or random.random() < math.exp(-delta / max(temp, 1e-10)):
                x = x_new
                current_val = new_val
                if current_val < best_val:
                    best_val = current_val
                    best_x = x.copy()
            temp = self._temperature(temp, iteration)
            if temp < self.schedule.min_temp:
                break
            self.history.append(best_val)
            if verbose and iteration % 100 == 0:
                print(f"Iter {iteration}, best: {best_val:.4f}, temp: {temp:.4f}")
        return best_x, best_val

# Example objective: Rosenbrock function
def rosenbrock(x: np.ndarray) -> float:
    return sum(100*(x[1:]-x[:-1]**2)**2 + (1-x[:-1])**2)

def sphere(x: np.ndarray) -> float:
    return np.sum(x**2)
