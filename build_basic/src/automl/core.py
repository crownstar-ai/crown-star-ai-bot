# automl/core.py – CrownStar AutoML & Hyperparameter Optimisation Engine
import os, json, time, math, random, hashlib, copy, uuid
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
import logging
import numpy as np
import threading
import concurrent.futures

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Models
# --------------------------------------------------------------------
class OptimisationAlgorithm(Enum):
    RANDOM = "random"
    BAYESIAN = "bayesian"
    HYPERBAND = "hyperband"
    BOHB = "bohb"

@dataclass
class SearchSpace:
    """Definition of hyperparameter search space."""
    name: str
    type: str  # "float", "int", "choice"
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[List[Any]] = None
    log_scale: bool = False

@dataclass
class Trial:
    trial_id: str
    status: str  # pending, running, completed, failed, pruned
    params: Dict[str, Any]
    objective: Optional[float] = None
    metrics: Optional[Dict] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    resources_used: Optional[float] = None
    error: Optional[str] = None

@dataclass
class OptimisationConfig:
    algorithm: OptimisationAlgorithm
    objective_name: str = "accuracy"
    direction: str = "maximize"
    total_trials: int = 50
    parallel_trials: int = 4
    max_epochs: int = 100
    early_stopping_rounds: int = 10
    seed: int = 42

# --------------------------------------------------------------------
# Surrogate Model (Gaussian Process) for Bayesian Optimisation
# --------------------------------------------------------------------
class GaussianProcessOptimiser:
    def __init__(self, search_space: List[SearchSpace], random_state: int = 42):
        self.search_space = search_space
        self.random_state = random_state
        self._gp = None
        self._X = []
        self._y = []
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
            from sklearn.gaussian_process.kernels import Matern, WhiteKernel
            kernel = Matern(nu=2.5) + WhiteKernel()
            self._gp = GaussianProcessRegressor(kernel=kernel, random_state=random_state)
            self.sklearn_available = True
        except ImportError:
            self.sklearn_available = False
            logger.warning("scikit-learn not installed, Bayesian optimisation will use random fallback")

    def _param_vector(self, params: Dict) -> List[float]:
        vec = []
        for space in self.search_space:
            val = params[space.name]
            if space.type == "float":
                vec.append((val - space.min) / (space.max - space.min) if space.max > space.min else 0.5)
            elif space.type == "int":
                vec.append((val - space.min) / (space.max - space.min) if space.max > space.min else 0.5)
            else:
                idx = space.choices.index(val) if val in space.choices else 0
                vec.append(idx / (len(space.choices) - 1) if len(space.choices) > 1 else 0.5)
        return vec

    def add_observation(self, params: Dict, objective: float):
        vec = self._param_vector(params)
        self._X.append(vec)
        self._y.append(objective)
        if self.sklearn_available and len(self._X) >= 3:
            self._gp.fit(np.array(self._X), np.array(self._y))

    def suggest(self) -> Dict:
        if not self.sklearn_available or len(self._X) < 2:
            return self._random_suggest()
        best_y = max(self._y) if self._y else 0
        candidates = []
        for _ in range(100):
            candidate = {}
            vec = []
            for space in self.search_space:
                if space.type == "float":
                    val = np.random.uniform(space.min, space.max)
                elif space.type == "int":
                    val = np.random.randint(space.min, space.max + 1)
                else:
                    val = np.random.choice(space.choices)
                candidate[space.name] = val
                vec.append(self._param_vector(candidate))
            mean, std = self._gp.predict(np.array([vec]), return_std=True)
            z = (mean - best_y) / (std + 1e-8)
            def norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
            def norm_pdf(x): return math.exp(-x*x/2) / math.sqrt(2*math.pi)
            ei = (mean - best_y) * norm_cdf(z) + std * norm_pdf(z)
            candidates.append((ei, candidate))
        if candidates:
            return max(candidates, key=lambda x: x[0])[1]
        return self._random_suggest()

    def _random_suggest(self) -> Dict:
        params = {}
        for space in self.search_space:
            if space.type == "float":
                params[space.name] = np.random.uniform(space.min, space.max)
            elif space.type == "int":
                params[space.name] = np.random.randint(space.min, space.max + 1)
            else:
                params[space.name] = np.random.choice(space.choices)
        return params

# --------------------------------------------------------------------
# Hyperband (simplified)
# --------------------------------------------------------------------
class HyperbandOptimiser:
    def __init__(self, search_space: List[SearchSpace], max_epochs: int = 100, eta: int = 3, random_state: int = 42):
        self.search_space = search_space
        self.max_epochs = max_epochs
        self.eta = eta
        self.random_state = random_state
        self.runs = {}

    def suggest(self) -> Tuple[Dict, int]:
        params = {}
        for space in self.search_space:
            if space.type == "float":
                params[space.name] = np.random.uniform(space.min, space.max)
            elif space.type == "int":
                params[space.name] = np.random.randint(space.min, space.max + 1)
            else:
                params[space.name] = np.random.choice(space.choices)
        return params, self.max_epochs

    def register_result(self, trial_id: str, objective: float, budget: int):
        self.runs[trial_id] = (self.runs.get(trial_id, (None, None))[0], budget, objective)

    def should_prune(self, trial_id: str, current_objective: float, current_budget: int, historical_results: Dict) -> bool:
        completed = [score for tid, (_, budget, score) in self.runs.items() if budget >= current_budget]
        if len(completed) < 5:
            return False
        median_score = np.median(completed)
        return current_objective < median_score

# --------------------------------------------------------------------
# AutoML Manager
# --------------------------------------------------------------------
class AutoMLManager:
    def __init__(self, config_path="config/automl/config.json"):
        self.config = self._load_config(config_path)
        self.active_optimisations: Dict[str, Dict] = {}
        self.trials: Dict[str, Trial] = {}
        self.best_trial: Optional[Trial] = None
        self._lock = threading.Lock()

    def _load_config(self, path):
        default = {
            "default_algorithm": "bayesian",
            "parallel_trials": 4,
            "max_epochs": 100,
            "early_stopping_rounds": 10,
            "objective_metric": "accuracy",
            "direction": "maximize",
            "storage_dir": "data/automl"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        os.makedirs(default["storage_dir"], exist_ok=True)
        return default

    def _save_trials(self, opt_id: str):
        path = os.path.join(self.config["storage_dir"], f"{opt_id}_trials.json")
        with open(path, 'w') as f:
            data = {tid: asdict(t) for tid, t in self.trials.items()}
            json.dump(data, f, indent=2)

    def _load_trials(self, opt_id: str):
        path = os.path.join(self.config["storage_dir"], f"{opt_id}_trials.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                for tid, tdict in data.items():
                    self.trials[tid] = Trial(**tdict)

    def start_optimisation(self, task_name: str, search_space: List[Dict], train_func: Callable,
                           algorithm: str = None, total_trials: int = None) -> str:
        opt_id = hashlib.md5(f"{task_name}_{time.time()}".encode()).hexdigest()[:16]
        alg = OptimisationAlgorithm(algorithm or self.config["default_algorithm"])
        total = total_trials or self.config.get("total_trials", 50)
        spaces = []
        for s in search_space:
            spaces.append(SearchSpace(
                name=s["name"],
                type=s["type"],
                min=s.get("min"),
                max=s.get("max"),
                choices=s.get("choices"),
                log_scale=s.get("log_scale", False)
            ))
        if alg == OptimisationAlgorithm.RANDOM:
            optimiser = None
        elif alg == OptimisationAlgorithm.BAYESIAN:
            optimiser = GaussianProcessOptimiser(spaces, random_state=self.config.get("seed", 42))
        elif alg in (OptimisationAlgorithm.HYPERBAND, OptimisationAlgorithm.BOHB):
            optimiser = HyperbandOptimiser(spaces, max_epochs=self.config["max_epochs"])
        else:
            optimiser = None

        self.active_optimisations[opt_id] = {
            "id": opt_id,
            "task": task_name,
            "algorithm": alg,
            "search_space": spaces,
            "train_func": train_func,
            "total_trials": total,
            "completed_trials": 0,
            "start_time": int(time.time()),
            "status": "running",
            "optimiser": optimiser,
            "best_objective": None
        }
        thread = threading.Thread(target=self._optimisation_worker, args=(opt_id,))
        thread.daemon = True
        thread.start()
        logger.info(f"Started optimisation {opt_id} with {alg.value}")
        return opt_id

    def _optimisation_worker(self, opt_id: str):
        opt = self.active_optimisations[opt_id]
        search_space = opt["search_space"]
        train_func = opt["train_func"]
        algorithm = opt["algorithm"]
        total_trials = opt["total_trials"]
        optimiser = opt["optimiser"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config["parallel_trials"]) as executor:
            futures = []
            for trial_idx in range(total_trials):
                if algorithm == OptimisationAlgorithm.RANDOM:
                    params = {}
                    for space in search_space:
                        if space.type == "float":
                            params[space.name] = np.random.uniform(space.min, space.max)
                        elif space.type == "int":
                            params[space.name] = np.random.randint(space.min, space.max + 1)
                        else:
                            params[space.name] = np.random.choice(space.choices)
                elif algorithm == OptimisationAlgorithm.BAYESIAN:
                    params = optimiser.suggest()
                else:
                    params, budget = optimiser.suggest()
                trial_id = f"{opt_id}_{trial_idx}"
                trial = Trial(
                    trial_id=trial_id,
                    status="pending",
                    params=params,
                    start_time=None,
                    end_time=None
                )
                self.trials[trial_id] = trial
                future = executor.submit(self._run_trial, opt_id, trial_id, params, train_func, algorithm)
                futures.append(future)
            for future in concurrent.futures.as_completed(futures):
                trial_id, objective, metrics = future.result()
                self._update_trial(trial_id, objective, metrics)
                opt["completed_trials"] += 1
                if algorithm == OptimisationAlgorithm.BAYESIAN and optimiser:
                    trial = self.trials[trial_id]
                    optimiser.add_observation(trial.params, objective)
                best = opt["best_objective"]
                direction = 1 if self.config["direction"] == "maximize" else -1
                if best is None or (direction * objective > direction * best):
                    opt["best_objective"] = objective
                    self.best_trial = trial
                self._save_trials(opt_id)
        opt["status"] = "completed"
        opt["end_time"] = int(time.time())
        logger.info(f"Optimisation {opt_id} completed, best objective: {opt['best_objective']}")

    def _run_trial(self, opt_id: str, trial_id: str, params: Dict, train_func: Callable, algorithm: str) -> Tuple[str, float, Dict]:
        trial = self.trials[trial_id]
        trial.status = "running"
        trial.start_time = int(time.time())
        try:
            objective, metrics = train_func(params, max_epochs=self.config["max_epochs"])
            trial.status = "completed"
            trial.objective = objective
            trial.metrics = metrics
        except Exception as e:
            trial.status = "failed"
            trial.error = str(e)
            objective = -float('inf') if self.config["direction"] == "maximize" else float('inf')
            metrics = {}
        finally:
            trial.end_time = int(time.time())
        return trial_id, objective, metrics

    def _update_trial(self, trial_id: str, objective: float, metrics: Dict):
        trial = self.trials[trial_id]
        trial.objective = objective
        trial.metrics = metrics
        if trial.status == "running":
            trial.status = "completed"
        trial.end_time = int(time.time())

    def get_status(self, opt_id: str) -> Dict:
        opt = self.active_optimisations.get(opt_id)
        if not opt:
            return {"error": "Not found"}
        return {
            "id": opt_id,
            "task": opt["task"],
            "algorithm": opt["algorithm"].value,
            "status": opt["status"],
            "completed_trials": opt["completed_trials"],
            "total_trials": opt["total_trials"],
            "best_objective": opt["best_objective"],
            "start_time": opt["start_time"],
            "end_time": opt.get("end_time")
        }

    def get_trials(self, opt_id: str) -> List[Trial]:
        return [t for t in self.trials.values() if t.trial_id.startswith(opt_id)]

    def get_best_trial(self, opt_id: str) -> Optional[Trial]:
        best_obj = None
        best_trial = None
        direction = 1 if self.config["direction"] == "maximize" else -1
        for trial in self.get_trials(opt_id):
            if trial.status == "completed" and trial.objective is not None:
                if best_obj is None or (direction * trial.objective > direction * best_obj):
                    best_obj = trial.objective
                    best_trial = trial
        return best_trial

_automl_manager = None
def get_automl_manager():
    global _automl_manager
    if _automl_manager is None:
        _automl_manager = AutoMLManager()
    return _automl_manager
