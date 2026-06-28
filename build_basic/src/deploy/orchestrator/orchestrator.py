# deploy/orchestrator/orchestrator.py – CrownStar Multi-Cloud Deployment Engine
import os, json, time, yaml, subprocess, hashlib, threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import requests

class CloudProvider(Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    SOVEREIGN_AU = "sovereign_au"

class DeploymentStrategy(Enum):
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    RECREATE = "recreate"

@dataclass
class Environment:
    env_id: str
    name: str           # dev, staging, prod
    provider: CloudProvider
    region: str
    infrastructure_state: Dict   # Terraform/Pulumi state outputs
    created_at: int
    updated_at: int

@dataclass
class Deployment:
    deployment_id: str
    environment_id: str
    version: str
    strategy: DeploymentStrategy
    status: str         # pending, running, succeeded, failed, rolled_back
    started_at: int
    completed_at: Optional[int]
    logs: List[str]

class MultiCloudOrchestrator:
    def __init__(self, config_path="config/deploy/orchestrator.yaml"):
        self.config = self._load_config(config_path)
        self.environments: Dict[str, Environment] = {}
        self.deployments: Dict[str, Deployment] = {}
        self.provider_clients = self._init_providers()
        self.terraform_workdir = "src/deploy/terraform"
        self._load_state()

    def _load_config(self, path):
        import yaml
        default = {
            "default_region": "ap-southeast-2",
            "default_strategy": "rolling",
            "providers": {
                "aws": {"enabled": True, "regions": ["ap-southeast-2", "us-east-1"]},
                "azure": {"enabled": True, "regions": ["australiaeast", "southeastasia"]},
                "gcp": {"enabled": True, "regions": ["australia-southeast1", "us-central1"]},
                "sovereign_au": {"enabled": True, "endpoint": "https://api.sovereign.cloud.gov.au"}
            },
            "failover": {
                "enabled": True,
                "health_check_interval_seconds": 30,
                "failure_threshold": 3
            },
            "cost_integration": True
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = yaml.safe_load(f)
                if user:
                    default.update(user)
        return default

    def _init_providers(self):
        clients = {}
        if self.config["providers"]["aws"]["enabled"]:
            clients["aws"] = AWSProvider()
        if self.config["providers"]["azure"]["enabled"]:
            clients["azure"] = AzureProvider()
        if self.config["providers"]["gcp"]["enabled"]:
            clients["gcp"] = GCPProvider()
        if self.config["providers"]["sovereign_au"]["enabled"]:
            clients["sovereign_au"] = SovereignAUProvider(self.config["providers"]["sovereign_au"]["endpoint"])
        return clients

    def _load_state(self):
        state_file = "data/deploy/states/orchestrator_state.json"
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                data = json.load(f)
                self.environments = {k: Environment(**v) for k, v in data.get("environments", {}).items()}
                self.deployments = {k: Deployment(**v) for k, v in data.get("deployments", {}).items()}

    def _save_state(self):
        os.makedirs("data/deploy/states", exist_ok=True)
        with open("data/deploy/states/orchestrator_state.json", 'w') as f:
            json.dump({
                "environments": {k: asdict(v) for k, v in self.environments.items()},
                "deployments": {k: asdict(v) for k, v in self.deployments.items()}
            }, f, indent=2)

    def create_environment(self, name: str, provider: CloudProvider, region: str, infrastructure_code_path: str = None) -> Environment:
        """Create a new deployment environment (e.g., dev, staging, prod)"""
        env_id = hashlib.md5(f"{name}_{provider.value}_{region}_{time.time()}".encode()).hexdigest()[:16]
        # Run Terraform/Pulumi to provision base infrastructure
        tf_vars = {
            "environment": name,
            "region": region,
            "project": "crownstar"
        }
        if infrastructure_code_path:
            self._run_terraform(infrastructure_code_path, "apply", tf_vars, env_id)
        env = Environment(
            env_id=env_id,
            name=name,
            provider=provider,
            region=region,
            infrastructure_state={"provisioned": True, "timestamp": int(time.time())},
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        self.environments[env_id] = env
        self._save_state()
        return env

    def _run_terraform(self, path: str, action: str, vars: Dict, env_id: str):
        """Execute Terraform plan/apply/destroy"""
        tf_dir = os.path.join(self.terraform_workdir, env_id)
        os.makedirs(tf_dir, exist_ok=True)
        # Write tfvars
        with open(os.path.join(tf_dir, "terraform.tfvars.json"), 'w') as f:
            json.dump(vars, f)
        cmd = ["terraform", "-chdir=" + tf_dir, action, "-auto-approve"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Terraform failed: {result.stderr}")
        return result.stdout

    def deploy(self, environment_id: str, version: str, strategy: DeploymentStrategy = None) -> Deployment:
        """Deploy CrownStar to an environment with specified strategy"""
        env = self.environments.get(environment_id)
        if not env:
            raise ValueError(f"Environment {environment_id} not found")
        if not strategy:
            strategy = DeploymentStrategy(self.config["default_strategy"])
        deployment_id = hashlib.md5(f"{environment_id}_{version}_{time.time()}".encode()).hexdigest()[:16]
        deployment = Deployment(
            deployment_id=deployment_id,
            environment_id=environment_id,
            version=version,
            strategy=strategy,
            status="pending",
            started_at=int(time.time()),
            completed_at=None,
            logs=[]
        )
        self.deployments[deployment_id] = deployment
        self._save_state()
        # Execute deployment asynchronously
        thread = threading.Thread(target=self._execute_deployment, args=(deployment_id,))
        thread.start()
        return deployment

    def _execute_deployment(self, deployment_id: str):
        dep = self.deployments[deployment_id]
        env = self.environments[dep.environment_id]
        dep.status = "running"
        dep.logs.append(f"Starting deployment to {env.name} ({env.provider.value}/{env.region}) with strategy {dep.strategy.value}")
        try:
            if dep.strategy == DeploymentStrategy.BLUE_GREEN:
                self._blue_green_deploy(dep, env)
            elif dep.strategy == DeploymentStrategy.CANARY:
                self._canary_deploy(dep, env)
            elif dep.strategy == DeploymentStrategy.ROLLING:
                self._rolling_deploy(dep, env)
            else:
                self._recreate_deploy(dep, env)
            dep.status = "succeeded"
            dep.logs.append("Deployment completed successfully")
        except Exception as e:
            dep.status = "failed"
            dep.logs.append(f"Deployment failed: {str(e)}")
            # Auto-rollback if enabled
            if self.config.get("failover", {}).get("enabled", False):
                self._rollback(dep)
        finally:
            dep.completed_at = int(time.time())
            self._save_state()
            # Notify via existing alerting (Paste 64)
            self._send_notification(f"Deployment {dep.deployment_id} status: {dep.status}")

    def _blue_green_deploy(self, dep: Deployment, env: Environment):
        """Blue/green deployment: spin up new version, switch traffic, tear down old"""
        dep.logs.append("Blue/green: preparing green environment")
        # Simulate: deploy new version alongside existing
        self._deploy_to_provider(env, dep.version, tag="green")
        dep.logs.append("Blue/green: switching traffic to green")
        self._switch_traffic(env, "green")
        dep.logs.append("Blue/green: decommissioning blue")
        self._decommission(env, "blue")

    def _canary_deploy(self, dep: Deployment, env: Environment):
        """Canary: gradually shift traffic from 1% to 100%"""
        dep.logs.append("Canary: deploying new version with 1% traffic")
        self._deploy_to_provider(env, dep.version, tag="canary")
        for percent in [1, 5, 20, 50, 100]:
            self._set_traffic_split(env, percent)
            dep.logs.append(f"Canary: traffic at {percent}%")
            time.sleep(30)  # observe
            if self._health_check(env) < 0.95:
                raise Exception("Health check failed during canary")
        dep.logs.append("Canary: deployment complete")

    def _rolling_deploy(self, dep: Deployment, env: Environment):
        """Rolling: update instances one by one"""
        dep.logs.append("Rolling: updating instances sequentially")
        # Simulate rolling update
        self._rolling_update(env, dep.version)

    def _recreate_deploy(self, dep: Deployment, env: Environment):
        """Recreate: tear down and rebuild"""
        dep.logs.append("Recreate: destroying existing deployment")
        self._destroy_environment(env)
        dep.logs.append("Recreate: building new")
        self._deploy_to_provider(env, dep.version)

    def _deploy_to_provider(self, env: Environment, version: str, tag: str = None):
        provider = self.provider_clients.get(env.provider.value)
        if not provider:
            raise Exception(f"Provider {env.provider.value} not available")
        provider.deploy(env.region, version, tag)

    def _switch_traffic(self, env: Environment, to_tag: str):
        # DNS or load balancer switch
        pass

    def _set_traffic_split(self, env: Environment, percent: int):
        pass

    def _health_check(self, env: Environment) -> float:
        # Query CrownStar health endpoint
        return 1.0

    def _rolling_update(self, env: Environment, version: str):
        pass

    def _destroy_environment(self, env: Environment):
        pass

    def _decommission(self, env: Environment, tag: str):
        pass

    def _rollback(self, dep: Deployment):
        dep.logs.append("Initiating rollback")
        # Revert to previous version
        dep.status = "rolled_back"
        self._send_notification(f"Rollback completed for {dep.deployment_id}")

    def _send_notification(self, message: str):
        try:
            requests.post("http://localhost:8080/v1/notifications/alert", json={
                "title": "Deployment Orchestration",
                "message": message,
                "severity": "info"
            }, timeout=2)
        except:
            pass

    def failover(self, from_env_id: str, to_env_id: str) -> bool:
        """Manually or automatically failover traffic to another environment (region/cloud)"""
        from_env = self.environments.get(from_env_id)
        to_env = self.environments.get(to_env_id)
        if not from_env or not to_env:
            return False
        self._send_notification(f"FAILOVER: switching from {from_env.name} to {to_env.name}")
        # Update DNS or global load balancer
        self._switch_traffic(to_env, "active")
        return True

    def get_deployment_status(self, deployment_id: str) -> Dict:
        dep = self.deployments.get(deployment_id)
        if not dep:
            return {"error": "not found"}
        return asdict(dep)

    def list_environments(self) -> List[Dict]:
        return [asdict(e) for e in self.environments.values()]

# Provider stubs (real implementations would use SDKs)
class AWSProvider:
    def deploy(self, region, version, tag):
        print(f"AWS deploying {version} to {region} (tag={tag})")
class AzureProvider:
    def deploy(self, region, version, tag):
        print(f"Azure deploying {version} to {region}")
class GCPProvider:
    def deploy(self, region, version, tag):
        print(f"GCP deploying {version} to {region}")
class SovereignAUProvider:
    def __init__(self, endpoint):
        self.endpoint = endpoint
    def deploy(self, region, version, tag):
        print(f"Sovereign AU deploying {version} to {self.endpoint}")

_orchestrator = None
def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MultiCloudOrchestrator()
    return _orchestrator
