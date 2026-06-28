# functions/core.py – CrownStar Edge Functions & Serverless Compute Engine
import os, json, time, hashlib, uuid, threading, queue, subprocess, tempfile, sys
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import requests

logger = logging.getLogger(__name__)

class FunctionRuntime(Enum):
    JAVASCRIPT = "javascript"; PYTHON = "python"; WASM = "wasm"

class FunctionTrigger(Enum):
    HTTP = "http"; SCHEDULE = "schedule"; STREAM = "stream"; WEBHOOK = "webhook"

@dataclass
class FunctionDefinition:
    function_id: str; name: str; runtime: FunctionRuntime; code: str; entrypoint: str
    triggers: List[Dict]; memory_mb: int = 128; timeout_seconds: int = 10
    environment: Dict = None; created_at: int = 0; updated_at: int = 0; version: int = 1

@dataclass
class FunctionInvocation:
    invocation_id: str; function_id: str; trigger: str; status: str
    duration_ms: float; memory_used_mb: float; error: Optional[str]; timestamp: int

@dataclass
class KVNamespace:
    namespace: str; function_id: str; entries: Dict[str, Any]

class FunctionSandbox:
    def __init__(self, func_def: FunctionDefinition):
        self.func_def = func_def; self.runtime = func_def.runtime
    def invoke(self, event: Dict, context: Dict) -> Dict:
        if self.runtime == FunctionRuntime.JAVASCRIPT: return self._invoke_js(event, context)
        elif self.runtime == FunctionRuntime.PYTHON: return self._invoke_python(event, context)
        elif self.runtime == FunctionRuntime.WASM: return self._invoke_wasm(event, context)
        else: return {"error": f"Unsupported runtime {self.runtime}"}
    def _invoke_js(self, event: Dict, context: Dict) -> Dict:
        try:
            from quickjs import Function
            js_code = self.func_def.code
            wrapped_code = f"""
            const handler = {self.func_def.entrypoint};
            const event = {json.dumps(event)};
            const context = {json.dumps(context)};
            const result = handler(event, context);
            result;
            """
            func = Function("handler", js_code + wrapped_code)
            result = func()
            return {"body": result}
        except ImportError:
            return self._run_nodejs(event, context)
    def _run_nodejs(self, event: Dict, context: Dict) -> Dict:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
            f.write(self.func_def.code)
            f.write(f"""
            const event = {json.dumps(event)};
            const context = {json.dumps(context)};
            const handler = {self.func_def.entrypoint};
            const result = handler(event, context);
            console.log(JSON.stringify(result));
            """)
            f.flush()
            try:
                output = subprocess.check_output(['node', f.name], timeout=self.func_def.timeout_seconds, stderr=subprocess.PIPE)
                result = json.loads(output.decode())
                return {"body": result}
            except subprocess.TimeoutExpired: return {"error": "Timeout"}
            except Exception as e: return {"error": str(e)}
            finally: os.unlink(f.name)
    def _invoke_python(self, event: Dict, context: Dict) -> Dict:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(self.func_def.code)
            f.write(f"\nimport json\n")
            f.write(f"event = {json.dumps(event)}\n")
            f.write(f"context = {json.dumps(context)}\n")
            f.write(f"result = {self.func_def.entrypoint}(event, context)\n")
            f.write(f"print(json.dumps(result))\n")
            f.flush()
            try:
                output = subprocess.check_output([sys.executable, f.name], timeout=self.func_def.timeout_seconds, stderr=subprocess.PIPE)
                result = json.loads(output.decode())
                return {"body": result}
            except subprocess.TimeoutExpired: return {"error": "Timeout"}
            except Exception as e: return {"error": str(e)}
            finally: os.unlink(f.name)
    def _invoke_wasm(self, event: Dict, context: Dict) -> Dict:
        return {"error": "WASM runtime not yet implemented"}

class KVStore:
    def __init__(self):
        self.namespaces: Dict[str, KVNamespace] = {}
    def get_namespace(self, namespace: str, function_id: str) -> KVNamespace:
        key = f"{function_id}:{namespace}"
        if key not in self.namespaces:
            self.namespaces[key] = KVNamespace(namespace=namespace, function_id=function_id, entries={})
        return self.namespaces[key]
    def get(self, namespace: str, key: str, function_id: str) -> Optional[Any]:
        ns = self.get_namespace(namespace, function_id); return ns.entries.get(key)
    def put(self, namespace: str, key: str, value: Any, function_id: str):
        ns = self.get_namespace(namespace, function_id); ns.entries[key] = value
    def delete(self, namespace: str, key: str, function_id: str) -> bool:
        ns = self.get_namespace(namespace, function_id)
        if key in ns.entries: del ns.entries[key]; return True
        return False

class FunctionScheduler:
    def __init__(self, engine): self.engine = engine; self._running = False; self._thread = None
    def start(self): self._running = True; self._thread = threading.Thread(target=self._schedule_loop, daemon=True); self._thread.start()
    def stop(self): self._running = False; if self._thread: self._thread.join(timeout=5)
    def _schedule_loop(self):
        from croniter import croniter
        jobs = []
        for fid, func in self.engine.functions.items():
            for trigger in func.triggers:
                if trigger.get("type") == "schedule":
                    jobs.append((trigger["cron"], fid))
        next_runs = []
        for cron, fid in jobs:
            cron_obj = croniter(cron, time.time())
            next_runs.append((cron_obj.get_next(float), cron_obj, fid))
        while self._running:
            now = time.time()
            for entry in next_runs[:]:
                if entry[0] <= now:
                    self.engine.invoke_function(entry[2], {"trigger": "schedule", "time": now}, {})
                    next_time = entry[1].get_next(float)
                    next_runs.remove(entry)
                    next_runs.append((next_time, entry[1], entry[2]))
            time.sleep(1)

class FunctionManager:
    def __init__(self, config_path="config/functions/config.json"):
        self.config = self._load_config(config_path)
        self.functions: Dict[str, FunctionDefinition] = {}
        self.kv = KVStore()
        self.scheduler = FunctionScheduler(self)
        self._invocation_log: List[FunctionInvocation] = []
        self._load_functions()
    def _load_config(self, path):
        default = {"default_memory_mb":128,"default_timeout_seconds":10,"max_function_size_kb":1024,"invocation_log_retention":10000,"kv_storage_dir":"data/functions/kv"}
        if os.path.exists(path):
            with open(path,'r') as f: default.update(json.load(f))
        os.makedirs(default["kv_storage_dir"], exist_ok=True)
        return default
    def _load_functions(self):
        func_dir = "data/functions"
        os.makedirs(func_dir, exist_ok=True)
        for fname in os.listdir(func_dir):
            if fname.endswith(".json"):
                with open(os.path.join(func_dir, fname),'r') as f:
                    data = json.load(f)
                    data["runtime"] = FunctionRuntime(data["runtime"])
                    self.functions[data["function_id"]] = FunctionDefinition(**data)
    def _save_function(self, func: FunctionDefinition):
        func_dir = "data/functions"
        with open(os.path.join(func_dir, f"{func.function_id}.json"),'w') as f:
            data = asdict(func)
            data["runtime"] = data["runtime"].value
            json.dump(data, f, indent=2)
    def deploy(self, name: str, runtime: str, code: str, entrypoint: str, triggers: List[Dict], memory_mb: int = None, timeout_seconds: int = None) -> str:
        func_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()[:16]
        if memory_mb is None: memory_mb = self.config["default_memory_mb"]
        if timeout_seconds is None: timeout_seconds = self.config["default_timeout_seconds"]
        func = FunctionDefinition(function_id=func_id, name=name, runtime=FunctionRuntime(runtime), code=code, entrypoint=entrypoint, triggers=triggers, memory_mb=memory_mb, timeout_seconds=timeout_seconds, environment={}, created_at=int(time.time()), updated_at=int(time.time()), version=1)
        self.functions[func_id] = func
        self._save_function(func)
        if any(t.get("type") == "schedule" for t in triggers): self.scheduler.start()
        return func_id
    def invoke_function(self, function_id: str, event: Dict, context: Dict = None) -> Dict:
        start = time.perf_counter()
        func = self.functions.get(function_id)
        if not func: return {"error": f"Function {function_id} not found"}
        sandbox = FunctionSandbox(func)
        try:
            result = sandbox.invoke(event, context or {})
            status = "success"
            error = None
        except Exception as e:
            result = {"error": str(e)}; status = "error"; error = str(e)
        duration_ms = (time.perf_counter() - start) * 1000
        invocation = FunctionInvocation(invocation_id=str(uuid.uuid4()), function_id=function_id, trigger=context.get("trigger","http") if context else "http", status=status, duration_ms=duration_ms, memory_used_mb=0.0, error=error, timestamp=int(time.time()))
        self._invocation_log.append(invocation)
        if len(self._invocation_log) > self.config["invocation_log_retention"]: self._invocation_log = self._invocation_log[-self.config["invocation_log_retention"]:]
        self._record_cost(function_id, duration_ms, status)
        return result
    def _record_cost(self, function_id: str, duration_ms: float, status: str):
        try:
            cost = duration_ms / 1000.0 * 0.000001
            if status != "success": cost = 0.0
            requests.post("http://localhost:8080/v1/cost/metrics", json={"resource_id": f"func_{function_id}","resource_type":"compute","provider":"edge","region":"global","hourly_cost":cost,"utilization_cpu":0,"utilization_memory":0,"utilization_disk":0,"timestamp":int(time.time())}, timeout=1)
        except: pass
    def get_function(self, function_id: str) -> Optional[FunctionDefinition]: return self.functions.get(function_id)
    def list_functions(self) -> List[FunctionDefinition]: return list(self.functions.values())
    def delete_function(self, function_id: str) -> bool:
        if function_id in self.functions:
            del self.functions[function_id]
            os.remove(f"data/functions/{function_id}.json")
            return True
        return False
    def get_logs(self, function_id: str = None, limit: int = 100) -> List[Dict]:
        if function_id: logs = [asdict(i) for i in self._invocation_log if i.function_id == function_id]
        else: logs = [asdict(i) for i in self._invocation_log]
        return logs[-limit:]
    def kv_get(self, namespace: str, key: str, function_id: str) -> Optional[Any]: return self.kv.get(namespace, key, function_id)
    def kv_put(self, namespace: str, key: str, value: Any, function_id: str): self.kv.put(namespace, key, value, function_id)
    def kv_delete(self, namespace: str, key: str, function_id: str) -> bool: return self.kv.delete(namespace, key, function_id)

_fn_manager = None
def get_fn_manager():
    global _fn_manager
    if _fn_manager is None: _fn_manager = FunctionManager()
    return _fn_manager
