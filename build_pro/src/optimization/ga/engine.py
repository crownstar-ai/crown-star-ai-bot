# optimization/ga/engine.py – Genetic Algorithm for optimization
import numpy as np
import random
from typing import Callable, Tuple, List, Optional
from dataclasses import dataclass

@dataclass
class GAParameters:
    population_size: int = 100
    generations: int = 200
    crossover_rate: float = 0.8
    mutation_rate: float = 0.1
    elite_ratio: float = 0.1
    selection: str = "tournament"  # tournament, roulette
    tournament_size: int = 3

class GeneticAlgorithm:
    def __init__(self, objective: Callable[[np.ndarray], float], bounds: np.ndarray, params: GAParameters = None):
        self.objective = objective
        self.bounds = bounds
        self.dim = bounds.shape[0]
        self.params = params or GAParameters()
        self.population = None
        self.fitness = None
        self.best_individual = None
        self.best_fitness = float('inf')
        self.history = []
    
    def _initialize_population(self):
        self.population = np.random.uniform(
            self.bounds[:,0], self.bounds[:,1],
            size=(self.params.population_size, self.dim)
        )
        self._evaluate_population()
    
    def _evaluate_population(self):
        self.fitness = np.array([self.objective(ind) for ind in self.population])
        # Track best
        min_idx = np.argmin(self.fitness)
        if self.fitness[min_idx] < self.best_fitness:
            self.best_fitness = self.fitness[min_idx]
            self.best_individual = self.population[min_idx].copy()
    
    def _tournament_selection(self) -> np.ndarray:
        idx = np.random.choice(len(self.population), size=self.params.tournament_size, replace=False)
        best = idx[np.argmin(self.fitness[idx])]
        return self.population[best].copy()
    
    def _roulette_selection(self) -> np.ndarray:
        # For minimization, invert fitness
        inv_fitness = 1.0 / (self.fitness + 1e-10)
        probs = inv_fitness / np.sum(inv_fitness)
        idx = np.random.choice(len(self.population), p=probs)
        return self.population[idx].copy()
    
    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if random.random() < self.params.crossover_rate:
            point = random.randint(1, self.dim-1)
            child1 = np.concatenate([parent1[:point], parent2[point:]])
            child2 = np.concatenate([parent2[:point], parent1[point:]])
            return child1, child2
        else:
            return parent1.copy(), parent2.copy()
    
    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        for i in range(self.dim):
            if random.random() < self.params.mutation_rate:
                individual[i] += np.random.normal(0, (self.bounds[i,1]-self.bounds[i,0]) * 0.1)
                individual[i] = np.clip(individual[i], self.bounds[i,0], self.bounds[i,1])
        return individual
    
    def optimize(self, verbose: bool = False) -> Tuple[np.ndarray, float]:
        self._initialize_population()
        elite_count = max(1, int(self.params.population_size * self.params.elite_ratio))
        for gen in range(self.params.generations):
            new_population = []
            # Elitism
            elite_idx = np.argsort(self.fitness)[:elite_count]
            for idx in elite_idx:
                new_population.append(self.population[idx].copy())
            # Fill rest
            while len(new_population) < self.params.population_size:
                # Selection
                if self.params.selection == "tournament":
                    p1 = self._tournament_selection()
                    p2 = self._tournament_selection()
                else:
                    p1 = self._roulette_selection()
                    p2 = self._roulette_selection()
                # Crossover
                c1, c2 = self._crossover(p1, p2)
                # Mutation
                c1 = self._mutate(c1)
                c2 = self._mutate(c2)
                new_population.append(c1)
                if len(new_population) < self.params.population_size:
                    new_population.append(c2)
            self.population = np.array(new_population[:self.params.population_size])
            self._evaluate_population()
            self.history.append(self.best_fitness)
            if verbose and gen % 20 == 0:
                print(f"Gen {gen}, best fitness: {self.best_fitness:.6f}")
        return self.best_individual, self.best_fitness
