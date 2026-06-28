# deploy/cost_aware_scheduler.py – Use cost optimization to choose cheapest region/cloud
from cost.optimizer.optimizer import get_optimizer
from .orchestrator.orchestrator import get_orchestrator, CloudProvider

class CostAwareScheduler:
    def __init__(self):
        self.cost_opt = get_optimizer()
        self.deploy_opt = get_orchestrator()

    def get_cheapest_region(self, preferred_providers=None):
        # Get recommendations and infer cheapest region from cost metrics
        recs = self.cost_opt.get_recommendations(100)
        # Very simplified: assume ap-southeast-2 is cheapest
        return {"provider": "aws", "region": "ap-southeast-2"}

    def deploy_cost_optimized(self, version: str):
        cheapest = self.get_cheapest_region()
        # Create or reuse environment
        envs = self.deploy_opt.list_environments()
        target = None
        for e in envs:
            if e["provider"] == cheapest["provider"] and e["region"] == cheapest["region"]:
                target = e["env_id"]
                break
        if not target:
            # create environment
            env = self.deploy_opt.create_environment("cost-optimized", CloudProvider(cheapest["provider"]), cheapest["region"])
            target = env.env_id
        deployment = self.deploy_opt.deploy(target, version)
        return deployment
