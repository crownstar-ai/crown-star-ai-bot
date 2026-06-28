# deepseek_adapter.py – DeepSeek V2‑Lite and V3
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from ..base_adapter import LanguageModelAdapter

class DeepSeekAdapter(LanguageModelAdapter):
    def __init__(self, model_version: str = "v2_lite", device: str = "auto"):
        self.model_version = model_version
        self.model_name = "deepseek-ai/DeepSeek-V3" if model_version == "v3" else "deepseek-ai/DeepSeek-V2-Lite"
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            trust_remote_code=True,
            device_map="auto" if device == "auto" else device
        )
        self.model.eval()
    async def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        gen_config = GenerationConfig(max_new_tokens=max_tokens, temperature=temperature, do_sample=True, pad_token_id=self.tokenizer.eos_token_id)
        with torch.no_grad():
            outputs = self.model.generate(**inputs, generation_config=gen_config)
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response[len(prompt):].strip() if response.startswith(prompt) else response
    def get_model_info(self) -> dict:
        return {"name": f"DeepSeek-{self.model_version}", "provider": "DeepSeek"}
