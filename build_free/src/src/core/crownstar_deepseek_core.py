# crownstar_deepseek_core.py – now includes CrownStar cognitive engine as a prefix
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from typing import Dict, Optional, Literal
import numpy as np
from .crownstar_cognitive import create_cognitive_engine

Tier = Literal["free", "basic", "pro", "enterprise"]

def detect_hardware():
    # (same as before, included for completeness)
    device = "cpu"
    dtype = torch.float32
    compile_model = False
    if torch.cuda.is_available():
        device = "cuda"
        dtype = torch.float16
        compile_model = True
    elif hasattr(torch, "version") and getattr(torch.version, "hip", None):
        device = "cuda"
        dtype = torch.float16
        compile_model = True
    else:
        dtype = torch.float32
        compile_model = False
    return device, dtype, compile_model

def get_model_name(tier: Tier) -> str:
    if tier in ("free", "basic"):
        return "deepseek-ai/DeepSeek-V2-Lite"
    else:
        return "deepseek-ai/DeepSeek-V3"

class CrownStarCognitiveWithDeepSeek:
    def __init__(self, tier: Tier = "free", modules_state: Optional[Dict[str, bool]] = None):
        self.tier = tier
        self.device, self.dtype, self.do_compile = detect_hardware()
        self.model_name = get_model_name(tier)
        # Load DeepSeek
        print(f"🔥 Loading DeepSeek: {self.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=self.dtype,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map="auto" if self.device == "cuda" else None
        ).to(self.device)
        if self.do_compile:
            try:
                self.model = torch.compile(self.model)
            except: pass
        self.model.eval()
        
        # Load CrownStar cognitive engine (small MLP)
        self.cognitive = create_cognitive_engine(input_dim=256, hidden_dims=[512,512,256])
        # For now, we need a simple text encoder to convert query to embedding.
        # Using a dummy placeholder – in production you would use a small sentence transformer.
        self.text_encoder = None  # TODO: add a real encoder
        
        self.modules_state = modules_state or {}
        for k, v in self.modules_state.items():
            self.cognitive.set_module(k, v)
        
        self.max_new_tokens = 256 if tier in ("free","basic") else 512
        self.temperature = 0.7
        self.min_length = 10
    
    def _encode_query(self, query: str) -> torch.Tensor:
        """Simple placeholder: convert query to a fixed random vector.
           Replace with a proper embedding model (e.g., sentence-transformers)."""
        # For demonstration, we use a deterministic hash.
        import hashlib
        h = hashlib.md5(query.encode()).hexdigest()
        vec = np.array([int(h[i:i+2], 16) for i in range(0, 32, 2)], dtype=np.float32)
        vec = vec / 255.0
        return torch.tensor(vec).unsqueeze(0)
    
    def answer_sync(self, query: str, modules_override: Optional[Dict[str, bool]] = None) -> str:
        if modules_override:
            for k, v in modules_override.items():
                self.cognitive.set_module(k, v)
        
        # Step 1: Cognitive engine produces a thought prefix
        query_emb = self._encode_query(query)
        thought_prefix = self.cognitive.produce_thought_prefix(query_emb)
        
        # Step 2: Build final prompt
        full_prompt = f"{thought_prefix}\nUser: {query}\nAssistant:"
        
        # Step 3: Generate with DeepSeek
        inputs = self.tokenizer(full_prompt, return_tensors="pt", truncation=True, max_length=4096).to(self.device)
        gen_config = GenerationConfig(
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_p=0.95,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
            min_new_tokens=self.min_length
        )
        with torch.no_grad():
            outputs = self.model.generate(**inputs, generation_config=gen_config)
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Remove prompt
        if response.startswith(full_prompt):
            response = response[len(full_prompt):].strip()
        else:
            if "Assistant:" in response:
                response = response.split("Assistant:", 1)[-1].strip()
        return response
    
    def get_available_modules(self):
        return list(self.cognitive.modules_state.keys())

# Alias for compatibility
CrownStarCognitive = CrownStarCognitiveWithDeepSeek
create_engine = CrownStarCognitiveWithDeepSeek
