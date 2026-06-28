# edge/export/converter.py – Convert CrownStar models to TFLite, ONNX, TensorRT
import os
import sys
import json
import torch
import numpy as np
from pathlib import Path
import subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from transformers import AutoModelForCausalLM, AutoTokenizer

class ModelExporter:
    def __init__(self, model_name: str = "deepseek-ai/DeepSeek-V2-Lite"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
    
    def load_model(self):
        print(f"Loading model {self.model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            trust_remote_code=True,
            device_map="auto" if self.device == "cuda" else None
        )
        self.model.eval()
    
    def export_to_onnx(self, output_path: str, opset_version: int = 14):
        """Export to ONNX format"""
        self.load_model()
        # Dummy input (batch=1, seq_len=32)
        dummy_input = torch.randint(0, 32000, (1, 32)).to(self.device)
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=['input_ids'],
            output_names=['logits'],
            dynamic_axes={'input_ids': {0: 'batch_size', 1: 'sequence_length'},
                         'logits': {0: 'batch_size', 1: 'sequence_length'}}
        )
        print(f"ONNX model saved to {output_path}")
        return output_path
    
    def export_to_tflite(self, output_path: str):
        """Convert ONNX -> TFLite via onnx2tf (requires onnx2tf)"""
        onnx_path = output_path.replace(".tflite", ".onnx")
        self.export_to_onnx(onnx_path)
        try:
            subprocess.run(["onnx2tf", "-i", onnx_path, "-o", output_path], check=True)
            print(f"TFLite model saved to {output_path}")
        except FileNotFoundError:
            print("onnx2tf not installed. Install with: pip install onnx2tf")
        return output_path
    
    def export_to_tensorrt(self, onnx_path: str, engine_path: str):
        """Build TensorRT engine from ONNX (requires NVIDIA TensorRT)"""
        try:
            import tensorrt as trt
            logger = trt.Logger(trt.Logger.WARNING)
            builder = trt.Builder(logger)
            network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
            parser = trt.OnnxParser(network, logger)
            with open(onnx_path, 'rb') as f:
                if not parser.parse(f.read()):
                    for i in range(parser.num_errors):
                        print(parser.get_error(i))
                    raise RuntimeError("ONNX parsing failed")
            config = builder.create_builder_config()
            config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 1 << 30)  # 1GB
            engine = builder.build_serialized_network(network, config)
            with open(engine_path, 'wb') as f:
                f.write(engine)
            print(f"TensorRT engine saved to {engine_path}")
        except ImportError:
            print("TensorRT not available. Install from NVIDIA.")
        return engine_path

class EdgeModelManager:
    def __init__(self, storage_dir: str = "models/edge"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def list_models(self):
        models = []
        for fmt in ["tflite", "onnx", "tensorrt"]:
            fmt_dir = self.storage_dir / fmt
            if fmt_dir.exists():
                for f in fmt_dir.glob("*"):
                    models.append({"name": f.name, "format": fmt, "size_mb": f.stat().st_size / (1024*1024)})
        return models
    
    def delete_model(self, model_name: str):
        for fmt in ["tflite", "onnx", "tensorrt"]:
            path = self.storage_dir / fmt / model_name
            if path.exists():
                path.unlink()
                return True
        return False

_edge_manager = None
def get_edge_manager():
    global _edge_manager
    if _edge_manager is None:
        _edge_manager = EdgeModelManager()
    return _edge_manager
