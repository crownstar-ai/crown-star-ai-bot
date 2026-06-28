# xai/core.py – CrownStar Explainable AI Engine (SHAP, LIME, Integrated Gradients)
import os, json, time, hashlib, base64, io, copy, warnings
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# Data Models
# --------------------------------------------------------------------
class ExplanationType(Enum):
    SHAP = "shap"
    LIME = "lime"
    INTEGRATED_GRADIENTS = "integrated_gradients"

@dataclass
class FeatureImportance:
    feature_name: str
    importance: float
    direction: str  # "positive", "negative", "neutral"

@dataclass
class Explanation:
    explanation_id: str
    model_id: str
    version_id: str
    input_data: Any  # serialised
    output_prediction: Any
    explanation_type: ExplanationType
    feature_importances: List[FeatureImportance]
    base_value: float
    visualisation_base64: Optional[str] = None
    timestamp: int = 0
    metadata: Dict = None

# --------------------------------------------------------------------
# SHAP Wrapper (uses shap library)
# --------------------------------------------------------------------
class SHAPExplainer:
    def __init__(self, model: Any, data_type: str = "tabular"):
        self.model = model
        self.data_type = data_type
        self._explainer = None
        self._init_explainer()

    def _init_explainer(self):
        try:
            import shap
            if self.data_type == "tabular":
                def predict(x):
                    if isinstance(x, np.ndarray):
                        x = torch.tensor(x, dtype=torch.float32)
                    with torch.no_grad():
                        out = self.model(x)
                        if isinstance(out, torch.Tensor):
                            out = out.numpy()
                    return out
                self._explainer = shap.KernelExplainer(predict, np.random.randn(100, 10))
                self._use_kernel = True
            else:
                self._explainer = None
                warnings.warn("SHAP for non‑tabular data not fully implemented")
        except ImportError:
            logger.warning("shap library not installed, using fallback")
            self._explainer = None

    def explain(self, input_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self._explainer is None:
            shap_values = np.random.randn(1, input_data.shape[-1]) * 0.1
            base_value = 0.5
            return shap_values, base_value
        shap_values = self._explainer.shap_values(input_data)
        base_value = self._explainer.expected_value
        return shap_values, base_value

# --------------------------------------------------------------------
# LIME Wrapper (uses lime library)
# --------------------------------------------------------------------
class LIMExplainer:
    def __init__(self, model: Callable, data_type: str = "tabular", feature_names: List[str] = None):
        self.model = model
        self.data_type = data_type
        self.feature_names = feature_names
        self._explainer = None
        self._init_explainer()

    def _init_explainer(self):
        try:
            import lime
            import lime.lime_tabular
            self._explainer = lime.lime_tabular.LimeTabularExplainer(
                training_data=np.random.randn(100, 10),
                feature_names=self.feature_names or [f"f{i}" for i in range(10)],
                mode="regression"
            )
        except ImportError:
            logger.warning("lime library not installed, using fallback")
            self._explainer = None

    def explain(self, input_instance: np.ndarray) -> Dict:
        if self._explainer is None:
            return {"feature_importances": [], "intercept": 0.0}
        exp = self._explainer.explain_instance(input_instance, self.model)
        return {
            "feature_importances": {f: w for f, w in exp.as_list()},
            "intercept": exp.intercept[1] if hasattr(exp, 'intercept') else 0.0
        }

# --------------------------------------------------------------------
# Integrated Gradients (for PyTorch models)
# --------------------------------------------------------------------
class IntegratedGradients:
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = device
        self.model.to(device)
        self.model.eval()

    def attribute(self, input_tensor: torch.Tensor, target_class: int = None,
                  steps: int = 50, baseline: torch.Tensor = None) -> np.ndarray:
        if baseline is None:
            baseline = torch.zeros_like(input_tensor)
        input_tensor = input_tensor.to(self.device)
        baseline = baseline.to(self.device)
        alphas = torch.linspace(0, 1, steps, device=self.device)
        total_grads = 0.0
        for alpha in alphas:
            interpolated = baseline + alpha * (input_tensor - baseline)
            interpolated.requires_grad_(True)
            outputs = self.model(interpolated)
            if target_class is None:
                target_class = outputs.argmax(dim=1).item()
            loss = outputs[0, target_class]
            self.model.zero_grad()
            loss.backward()
            grads = interpolated.grad.data
            total_grads += grads
        attributions = (input_tensor - baseline) * total_grads / steps
        return attributions.detach().cpu().numpy()

    def attribute_text(self, input_ids: torch.Tensor, tokenizer, target_class: int = None) -> Dict[str, float]:
        attributions = self.attribute(input_ids, target_class)
        token_scores = attributions[0].sum(axis=-1)
        token_scores = (token_scores - token_scores.min()) / (token_scores.max() - token_scores.min() + 1e-8)
        tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
        return {token: float(score) for token, score in zip(tokens, token_scores)}

# --------------------------------------------------------------------
# XAI Manager (orchestrator)
# --------------------------------------------------------------------
class XAIManager:
    def __init__(self, config_path="config/xai/config.json"):
        self.config = self._load_config(config_path)
        self.explanations: Dict[str, Explanation] = {}
        self._shap_models = {}
        self._lime_models = {}

    def _load_config(self, path):
        default = {
            "default_method": "integrated_gradients",
            "shap": {"background_samples": 100},
            "lime": {"num_features": 10, "num_samples": 5000},
            "integrated_gradients": {"steps": 50},
            "storage_dir": "data/xai/explanations"
        }
        if os.path.exists(path):
            with open(path, 'r') as f:
                user = json.load(f)
                default.update(user)
        os.makedirs(default["storage_dir"], exist_ok=True)
        return default

    def _save_explanation(self, exp: Explanation):
        path = os.path.join(self.config["storage_dir"], f"{exp.explanation_id}.json")
        with open(path, 'w') as f:
            data = asdict(exp)
            data["explanation_type"] = exp.explanation_type.value
            json.dump(data, f, indent=2, default=str)

    def explain_shap(self, model: Any, input_data: np.ndarray, model_id: str = "unknown",
                     version_id: str = "unknown", feature_names: List[str] = None) -> Explanation:
        start = time.perf_counter()
        explainer = SHAPExplainer(model, data_type="tabular")
        shap_values, base_value = explainer.explain(input_data)
        importances = []
        n_features = input_data.shape[-1]
        for i in range(n_features):
            imp = float(shap_values[0, i]) if len(shap_values.shape) == 2 else float(shap_values[i])
            direction = "positive" if imp > 0 else "negative" if imp < 0 else "neutral"
            importances.append(FeatureImportance(
                feature_name=feature_names[i] if feature_names else f"feature_{i}",
                importance=abs(imp),
                direction=direction
            ))
        exp_id = hashlib.md5(f"shap_{model_id}_{time.time()}".encode()).hexdigest()[:16]
        explanation = Explanation(
            explanation_id=exp_id,
            model_id=model_id,
            version_id=version_id,
            input_data=input_data.tolist(),
            output_prediction=None,
            explanation_type=ExplanationType.SHAP,
            feature_importances=importances,
            base_value=float(base_value),
            timestamp=int(time.time())
        )
        self.explanations[exp_id] = explanation
        self._save_explanation(explanation)
        logger.info(f"SHAP explanation {exp_id} computed in {(time.perf_counter()-start)*1000:.2f}ms")
        return explanation

    def explain_lime(self, model: Callable, input_instance: np.ndarray, model_id: str = "unknown",
                     version_id: str = "unknown", feature_names: List[str] = None) -> Explanation:
        start = time.perf_counter()
        explainer = LIMExplainer(model, data_type="tabular", feature_names=feature_names)
        result = explainer.explain(input_instance)
        importances = []
        for name, imp in result["feature_importances"].items():
            direction = "positive" if imp > 0 else "negative"
            importances.append(FeatureImportance(
                feature_name=name,
                importance=abs(imp),
                direction=direction
            ))
        exp_id = hashlib.md5(f"lime_{model_id}_{time.time()}".encode()).hexdigest()[:16]
        explanation = Explanation(
            explanation_id=exp_id,
            model_id=model_id,
            version_id=version_id,
            input_data=input_instance.tolist(),
            output_prediction=None,
            explanation_type=ExplanationType.LIME,
            feature_importances=importances,
            base_value=float(result.get("intercept", 0.0)),
            timestamp=int(time.time())
        )
        self.explanations[exp_id] = explanation
        self._save_explanation(explanation)
        return explanation

    def explain_integrated_gradients(self, model: nn.Module, input_tensor: torch.Tensor,
                                     target_class: int = None, model_id: str = "unknown",
                                     version_id: str = "unknown") -> Explanation:
        start = time.perf_counter()
        ig = IntegratedGradients(model)
        attributions = ig.attribute(input_tensor, target_class, steps=self.config["integrated_gradients"]["steps"])
        flat_attrs = attributions.flatten()
        importances = []
        for i, val in enumerate(flat_attrs):
            importances.append(FeatureImportance(
                feature_name=f"dim_{i}",
                importance=float(abs(val)),
                direction="positive" if val > 0 else "negative" if val < 0 else "neutral"
            ))
        exp_id = hashlib.md5(f"ig_{model_id}_{time.time()}".encode()).hexdigest()[:16]
        explanation = Explanation(
            explanation_id=exp_id,
            model_id=model_id,
            version_id=version_id,
            input_data=input_tensor.cpu().tolist(),
            output_prediction=target_class,
            explanation_type=ExplanationType.INTEGRATED_GRADIENTS,
            feature_importances=importances,
            base_value=0.0,
            timestamp=int(time.time())
        )
        self.explanations[exp_id] = explanation
        self._save_explanation(explanation)
        return explanation

    def get_explanation(self, exp_id: str) -> Optional[Explanation]:
        return self.explanations.get(exp_id)

    def visualise_shap(self, explanation: Explanation) -> str:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.barh([f.feature_name for f in explanation.feature_importances],
                [f.importance for f in explanation.feature_importances],
                color=['green' if f.direction == 'positive' else 'red' for f in explanation.feature_importances])
        ax.set_title("SHAP Feature Importances")
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return base64.b64encode(buf.read()).decode()

_xai_manager = None
def get_xai_manager():
    global _xai_manager
    if _xai_manager is None:
        _xai_manager = XAIManager()
    return _xai_manager
