# optimization/examples.py – Example problems solved with CrownStar optimizers
import numpy as np
from .qubo.solver import QUBOSolver, QUBOProblem
from .sa.engine import SimulatedAnnealing

def travelling_salesman_qubo(distances: np.ndarray) -> QUBOProblem:
    """Convert TSP to QUBO (simplified, uses penalty formulation)"""
    n = distances.shape[0]
    # QUBO size: n^2 (city, position)
    # This is a simplified stub – full implementation is complex
    Q = np.random.randn(n*n, n*n) * 0.01
    return QUBOProblem(Q, n*n, "TSP")

def knapsack_qubo(values: np.ndarray, weights: np.ndarray, capacity: float) -> QUBOProblem:
    """Convert 0-1 knapsack to QUBO using penalty method"""
    n = len(values)
    # Penalty for exceeding capacity
    penalty = 100.0
    Q = np.zeros((n, n))
    for i in range(n):
        Q[i,i] = -values[i] + penalty * weights[i]**2
        for j in range(i+1, n):
            Q[i,j] += penalty * 2 * weights[i] * weights[j]
            Q[j,i] = Q[i,j]
    # Add constant term for capacity
    # Simplified, ignoring constant
    return QUBOProblem(Q, n, "Knapsack")

def continuous_ackley(x: np.ndarray) -> float:
    """Ackley function (continuous, many local minima)"""
    a = 20
    b = 0.2
    c = 2 * np.pi
    d = len(x)
    sum1 = np.sum(x**2)
    sum2 = np.sum(np.cos(c * x))
    return -a * np.exp(-b * np.sqrt(sum1 / d)) - np.exp(sum2 / d) + a + np.exp(1)
