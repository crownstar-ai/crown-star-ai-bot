# finetune/trainer/mlflow_callback.py – Auto‑log fine‑tuning runs to MLflow
import mlflow
from ..service import get_finetune_service

def log_training_run(job_id: str, base_model: str, hyperparams: dict, metrics: dict, artifact_path: str):
    mlflow_service = get_mlflow_service()
    exp_id = mlflow_service.get_or_create_experiment("crownstar_finetuning")
    with mlflow.start_run(experiment_id=exp_id, run_name=f"job_{job_id}"):
        mlflow.log_params({"base_model": base_model, **hyperparams})
        mlflow.log_metrics(metrics)
        mlflow.log_artifacts(artifact_path, artifact_path="model")
        mlflow.register_model(f"runs:/{mlflow.active_run().info.run_id}/model", f"crownstar_{base_model.replace('/', '_')}")
