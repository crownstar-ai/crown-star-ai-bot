# src/core/unified_model.py – Dummy but loadable
import torch.nn as nn
class UnifiedSuperModel(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        self.dummy = nn.Linear(10, 10)
    def forward(self, x):
        return self.dummy(x)
class UnifiedModelConfig:
    def __init__(self, **kwargs):
        for k,v in kwargs.items(): setattr(self, k, v)
