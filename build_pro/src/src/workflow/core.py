# workflow/core.py – CrownStar Advanced Scheduling & Workflow Orchestration Engine
import os, json, time, hashlib, asyncio, threading, queue
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
from datetime import datetime, timedelta
import logging
import importlib
import inspect
import traceback

logger = logging.getLogger(__name__)

class TaskState(Enum):
    PENDING = "pending"; RUNNING = "running"; SUCCESS = "success"; FAILED = "failed"; SKIPPED = "skipped"; RETRY = "retry"

class WorkflowState(Enum):
    CREATED = "created"; RUNNING = "running"; SUCCESS = "success"; FAILED = "failed"; PAUSED = "paused"

class TriggerType(Enum):
    CRON = "cron"; INTERVAL = "interval"; WEBHOOK = "webhook"; FILE = "file"; DEPENDENCY = "dependency"

@dataclass
class TaskDefinition:
    task_id: str; name: str; function: str; dependencies: List[str] = None
    retries: int = 0; retry_delay_seconds: int = 60; timeout_seconds: int = 3600
    resources: Dict = None; params: Dict = None

@dataclass
class WorkflowDefinition:
    workflow_id: str; name: str; tasks: List[TaskDefinition]; schedule: Optional[str] = None
    trigger: Optional[TriggerType] = None; trigger_config: Dict = None; concurrency_limit: int = 1; tags: List[str] = None

@dataclass
class WorkflowInstance:
    instance_id: str; workflow_id: str; state: WorkflowState; started_at: int; finished_at: Optional[int]
    tasks: Dict[str, TaskState]; task_results: Dict[str, Any]; task_errors: Dict[str, str]; metadata: Dict = None

class TaskExecutor:
    def __init__(self, config: Dict):
        self.config = config; self.executor_type = config.get("executor", "local")
    def run_task(self, task: TaskDefinition, context: Dict) -> Any:
        if self.executor_type == "local":
            return self._run_local(task, context)
        else:
            return self._run_remote(task, context)
    def _run_local(self, task: TaskDefinition, context: Dict) -> Any:
        module_path, func_name = task.function.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        kwargs = task.params or {}
        kwargs["context"] = context
        return func(**kwargs)
    def _run_remote(self, task: TaskDefinition, context: Dict) -> Any:
        logger.info(f"Remote execution of {task.task_id} (stub)")
        return None

class WorkflowEngine:
    def __init__(self, config_path="config/workflow/config.json"):
        self.config = self._load_config(config_path)
        self.definitions: Dict[str, WorkflowDefinition] = {}
        self.instances: Dict[str, WorkflowInstance] = {}
        self.executor = TaskExecutor(self.config.get("executor", {}))
        self._lock = threading.Lock()
        self._load_definitions()
    def _load_config(self, path):
        default = {"executor":{"executor":"local"},"storage_dir":"data/workflow","max_concurrent_workflows":10,"default_retries":0,"default_timeout":3600}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        os.makedirs(default["storage_dir"], exist_ok=True)
        return default
    def _load_definitions(self):
        def_dir = os.path.join(self.config["storage_dir"], "definitions")
        os.makedirs(def_dir, exist_ok=True)
        for fname in os.listdir(def_dir):
            if fname.endswith(".json"):
                with open(os.path.join(def_dir, fname), 'r') as f:
                    data = json.load(f)
                    self.definitions[data["workflow_id"]] = self._dict_to_definition(data)
    def _save_definition(self, wf_def: WorkflowDefinition):
        def_dir = os.path.join(self.config["storage_dir"], "definitions")
        with open(os.path.join(def_dir, f"{wf_def.workflow_id}.json"), 'w') as f:
            json.dump(asdict(wf_def), f, indent=2)
    def _dict_to_definition(self, data) -> WorkflowDefinition:
        tasks = [TaskDefinition(**t) for t in data["tasks"]]
        trigger = TriggerType(data["trigger"]) if data.get("trigger") else None
        return WorkflowDefinition(workflow_id=data["workflow_id"],name=data["name"],tasks=tasks,schedule=data.get("schedule"),trigger=trigger,trigger_config=data.get("trigger_config",{}),concurrency_limit=data.get("concurrency_limit",1),tags=data.get("tags",[]))
    def register_workflow(self, definition: WorkflowDefinition) -> str:
        if definition.workflow_id in self.definitions: raise ValueError(f"Workflow {definition.workflow_id} exists")
        self.definitions[definition.workflow_id] = definition
        self._save_definition(definition)
        return definition.workflow_id
    def trigger_workflow(self, workflow_id: str, metadata: Dict = None) -> str:
        if workflow_id not in self.definitions: raise ValueError(f"Workflow {workflow_id} not found")
        wf_def = self.definitions[workflow_id]
        instance_id = hashlib.md5(f"{workflow_id}_{time.time()}_{metadata}".encode()).hexdigest()[:16]
        instance = WorkflowInstance(instance_id=instance_id, workflow_id=workflow_id, state=WorkflowState.RUNNING, started_at=int(time.time()), finished_at=None, tasks={t.task_id: TaskState.PENDING for t in wf_def.tasks}, task_results={}, task_errors={}, metadata=metadata)
        self.instances[instance_id] = instance
        threading.Thread(target=self._run_workflow, args=(instance_id,), daemon=True).start()
        return instance_id
    def _run_workflow(self, instance_id: str):
        instance = self.instances[instance_id]
        wf_def = self.definitions[instance.workflow_id]
        task_map = {t.task_id: t for t in wf_def.tasks}
        in_degree = {}; adjacency = {}
        for t in wf_def.tasks:
            in_degree[t.task_id] = len(t.dependencies)
            adjacency[t.task_id] = []
        for t in wf_def.tasks:
            for dep in t.dependencies:
                adjacency[dep].append(t.task_id)
        ready = deque([tid for tid, deg in in_degree.items() if deg == 0])
        completed = set()
        failed = False
        while ready and not failed:
            task_id = ready.popleft()
            task_def = task_map[task_id]
            instance.tasks[task_id] = TaskState.RUNNING
            for attempt in range(task_def.retries + 1):
                try:
                    context = {"workflow_instance_id": instance_id, "workflow_id": instance.workflow_id, "task_id": task_id, "results": instance.task_results, "metadata": instance.metadata}
                    result = self.executor.run_task(task_def, context)
                    instance.task_results[task_id] = result
                    instance.tasks[task_id] = TaskState.SUCCESS
                    break
                except Exception as e:
                    if attempt < task_def.retries:
                        time.sleep(task_def.retry_delay_seconds)
                    else:
                        instance.task_errors[task_id] = str(e)
                        instance.tasks[task_id] = TaskState.FAILED
                        failed = True
            if not failed:
                completed.add(task_id)
                for succ in adjacency.get(task_id, []):
                    in_degree[succ] -= 1
                    if in_degree[succ] == 0:
                        ready.append(succ)
        instance.state = WorkflowState.FAILED if failed else WorkflowState.SUCCESS
        instance.finished_at = int(time.time())
        self._save_instance(instance)
    def _save_instance(self, instance: WorkflowInstance):
        inst_dir = os.path.join(self.config["storage_dir"], "instances")
        os.makedirs(inst_dir, exist_ok=True)
        with open(os.path.join(inst_dir, f"{instance.instance_id}.json"), 'w') as f:
            json.dump(asdict(instance), f, indent=2)
    def get_status(self, instance_id: str) -> Optional[Dict]:
        if instance_id in self.instances: return asdict(self.instances[instance_id])
        path = os.path.join(self.config["storage_dir"], "instances", f"{instance_id}.json")
        if os.path.exists(path):
            with open(path, 'r') as f: return json.load(f)
        return None
    def list_workflows(self) -> List[Dict]: return [asdict(w) for w in self.definitions.values()]
    def list_instances(self, workflow_id: str = None) -> List[Dict]:
        inst_dir = os.path.join(self.config["storage_dir"], "instances")
        results = []
        for fname in os.listdir(inst_dir):
            if fname.endswith(".json"):
                with open(os.path.join(inst_dir, fname), 'r') as f:
                    data = json.load(f)
                    if workflow_id is None or data["workflow_id"] == workflow_id:
                        results.append(data)
        return results

class WorkflowScheduler:
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine; self._running = False; self._cron_jobs = []
    def start(self): self._running = True; threading.Thread(target=self._scheduler_loop, daemon=True).start(); logger.info("Workflow scheduler started")
    def stop(self): self._running = False
    def add_cron(self, cron_expr: str, workflow_id: str, metadata: Dict = None):
        self._cron_jobs.append((cron_expr, workflow_id, metadata))
    def _scheduler_loop(self):
        from croniter import croniter
        next_runs = []
        for expr, wf_id, meta in self._cron_jobs:
            cron = croniter(expr, datetime.now()); next_time = cron.get_next(datetime)
            next_runs.append((next_time, expr, wf_id, meta))
        while self._running:
            now = datetime.now()
            for entry in next_runs[:]:
                if entry[0] <= now:
                    self.engine.trigger_workflow(entry[2], entry[3])
                    cron = croniter(entry[1], now); next_time = cron.get_next(datetime)
                    next_runs.remove(entry)
                    next_runs.append((next_time, entry[1], entry[2], entry[3]))
            time.sleep(1)

_workflow_engine = None
_scheduler = None
def get_workflow_engine():
    global _workflow_engine, _scheduler
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
        _scheduler = WorkflowScheduler(_workflow_engine)
        _scheduler.start()
    return _workflow_engine
def get_scheduler(): return _scheduler
