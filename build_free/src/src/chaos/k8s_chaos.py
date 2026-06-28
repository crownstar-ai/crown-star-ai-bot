# chaos/k8s_chaos.py – Kubernetes chaos injection stubs (Litmus, Chaos Mesh)
import subprocess
import yaml
import tempfile

class KubernetesChaos:
    @staticmethod
    def apply_litmus_experiment(experiment_name: str, namespace: str = "crownstar"):
        """Apply Litmus chaos experiment (requires Litmus installed)"""
        # Example experiment YAML
        exp_yaml = f'''
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: crownstar-chaos
  namespace: {namespace}
spec:
  appinfo:
    appns: {namespace}
    applabel: "app=crownstar-api"
    appkind: deployment
  chaosServiceAccount: litmus
  experiments:
    - name: {experiment_name}
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "30"
            - name: CHAOS_INTERVAL
              value: "10"
        probe:
          - name: "check-frontend-access"
            type: "httpProbe"
            httpProbe/inputs:
              url: "http://crownstar-api:8080/v1/health"
              insecureSkipVerify: false
              responseTimeout: 3
        '''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(exp_yaml)
            tmpfile = f.name
        subprocess.run(["kubectl", "apply", "-f", tmpfile], check=False)
    
    @staticmethod
    def apply_chaos_mesh(pod_selector: str, chaos_type: str = "pod-kill"):
        """Apply Chaos Mesh experiment"""
        exp_yaml = f'''
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: crownstar-pod-kill
  namespace: crownstar
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - crownstar
    labelSelectors:
      app: crownstar-api
  duration: 30s
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(exp_yaml)
            tmpfile = f.name
        subprocess.run(["kubectl", "apply", "-f", tmpfile], check=False)
