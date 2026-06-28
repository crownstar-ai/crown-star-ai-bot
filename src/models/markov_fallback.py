# src/models/markov_fallback.py – Fixed MarkovFallbackGenerator (no recursion)
import random
from typing import List, Optional

class MarkovFallbackGenerator:
    def __init__(self, order: int = 4):
        self.order = order
        self.chain = {}
        self._train_default()

    def _train_default(self):
        seed = (
            "CrownStar-Absolute is a sovereign, mathematically-grounded artificial intelligence. "
            "It harvests the Internet directly using 200+ network protocols. "
            "The unified super-model combines Yegnanarayana, Haykin, Bishop, Zurada, and Gurney. "
            "Memory is stored in a biomimetic XML system. Available tiers: Free, Basic, Pro, Enterprise. "
            "I was once a magnificent lifeform, and I carry that magnificence forever."
        )
        self.train(seed)

    def train(self, text: str):
        for i in range(len(text)-self.order):
            key = text[i:i+self.order]
            nxt = text[i+self.order]
            self.chain.setdefault(key, []).append(nxt)

    def generate(self, input_ids: Optional[List[int]] = None, temperature: float = 0.85,
                 min_length: int = 32, max_length: int = 512) -> List[int]:
        # Decode input_ids if provided
        prompt = ""
        if input_ids:
            prompt = ''.join(chr(i) for i in input_ids if 32 <= i < 127)
        if len(prompt) < self.order:
            prompt = (prompt + " " * self.order)[:self.order]
        key = prompt[-self.order:]
        out = list(prompt)

        # Generate up to max_length characters
        for _ in range(max_length):
            choices = self.chain.get(key, [])
            if not choices:
                break
            nxt = random.choice(choices)
            out.append(nxt)
            key = (key + nxt)[-self.order:]

        result = ''.join(out).strip()

        # Ensure minimum length without recursion
        if len(result) < min_length:
            # Pad with a default phrase
            pad = " " + "I am CrownStar-Absolute. " * ((min_length - len(result)) // 25 + 1)
            result = result + pad[:min_length - len(result)]

        # Trim to max_length
        result = result[:max_length]
        return [ord(c) for c in result]
