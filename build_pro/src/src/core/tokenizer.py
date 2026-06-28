# src/core/tokenizer.py – Full BPETokenizer (BPE, training, encode/decode, save/load)
import json
import regex as re
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
from pathlib import Path

class BPETokenizer:
    GPT2_PATTERN = r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+"""
    
    def __init__(self, vocab_size: int = 50257, special_tokens: Dict[str, int] = None):
        self.vocab_size = vocab_size
        self.special_tokens = special_tokens or {"<pad>": 0, "<s>": 1, "</s>": 2, "<unk>": 3, "<mask>": 4}
        self.next_id = max(self.special_tokens.values()) + 1
        self.vocab = self.special_tokens.copy()
        self.id_to_token = {v: k for k, v in self.vocab.items()}
        self.merges = {}  # pair -> new token
        self.byte_encoder = self._build_byte_encoder()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}
        self.pattern = re.compile(self.GPT2_PATTERN)
        self._cache = {}

    def _build_byte_encoder(self):
        bs = list(range(ord("!"), ord("~")+1)) + list(range(ord("¡"), ord("¬")+1)) + list(range(ord("®"), ord("ÿ")+1))
        cs = bs[:]
        n = 0
        for b in range(2**8):
            if b not in bs:
                bs.append(b)
                cs.append(2**8 + n)
                n += 1
        return {chr(c): chr(b) for c, b in zip(cs, bs)}

    def _get_pairs(self, word):
        pairs = set()
        prev_char = word[0]
        for char in word[1:]:
            pairs.add((prev_char, char))
            prev_char = char
        return pairs

    def train(self, texts: List[str], min_frequency: int = 2, verbose: bool = False):
        word_freqs = defaultdict(int)
        for text in texts:
            for match in self.pattern.finditer(text):
                word = match.group()
                word_freqs[word] += 1
        splits = {word: list(word) for word in word_freqs}
        merges = {}
        vocab = set(ch for word in splits for ch in splits[word])
        for _ in range(self.vocab_size - len(self.vocab)):
            pair_freqs = defaultdict(int)
            for word, freq in word_freqs.items():
                symbols = splits[word]
                for pair in self._get_pairs(symbols):
                    pair_freqs[pair] += freq
            if not pair_freqs:
                break
            best_pair = max(pair_freqs, key=pair_freqs.get)
            if pair_freqs[best_pair] < min_frequency:
                break
            merges[best_pair] = self.next_id
            self.vocab[best_pair[0] + best_pair[1]] = self.next_id
            self.id_to_token[self.next_id] = best_pair[0] + best_pair[1]
            self.next_id += 1
            new_splits = {}
            for word, symbols in splits.items():
                new_symbols = []
                i = 0
                while i < len(symbols):
                    if i < len(symbols)-1 and (symbols[i], symbols[i+1]) == best_pair:
                        new_symbols.append(best_pair[0] + best_pair[1])
                        i += 2
                    else:
                        new_symbols.append(symbols[i])
                        i += 1
                new_splits[word] = new_symbols
            splits = new_splits
            if verbose:
                print(f"Merge {len(merges)}: {best_pair} -> {pair_freqs[best_pair]}")

    def encode(self, text: str, add_special_tokens: bool = True) -> List[int]:
        if text in self._cache:
            return self._cache[text]
        words = self.pattern.findall(text)
        encoded = []
        for word in words:
            bword = ''.join(self.byte_encoder.get(c, c) for c in word)
            tokens = list(bword)
            while len(tokens) > 1:
                min_pair = None
                min_idx = None
                for i in range(len(tokens)-1):
                    pair = (tokens[i], tokens[i+1])
                    if pair in self.merges:
                        if min_pair is None or self.merges[pair] < self.merges[min_pair]:
                            min_pair = pair
                            min_idx = i
                if min_pair is None:
                    break
                tokens = tokens[:min_idx] + [min_pair[0] + min_pair[1]] + tokens[min_idx+2:]
            for token in tokens:
                if token in self.vocab:
                    encoded.append(self.vocab[token])
                else:
                    encoded.append(self.vocab["<unk>"])
        if add_special_tokens:
            encoded = [self.vocab["<s>"]] + encoded + [self.vocab["</s>"]]
        self._cache[text] = encoded
        return encoded

    def decode(self, ids: List[int], skip_special_tokens: bool = True) -> str:
        tokens = []
        for i in ids:
            token = self.id_to_token.get(i, "<unk>")
            if skip_special_tokens and token in {"<pad>", "<s>", "</s>", "<unk>", "<mask>"}:
                continue
            tokens.append(token)
        text = ''.join(tokens)
        decoded = ''.join(self.byte_decoder.get(c, c) for c in text)
        return decoded

    def get_vocab_size(self) -> int:
        return len(self.vocab)

    def save(self, path: str):
        data = {
            "vocab": self.vocab,
            "merges": {f"{k[0]}|{k[1]}": v for k, v in self.merges.items()},
            "next_id": self.next_id,
            "special_tokens": self.special_tokens
        }
        with open(path, 'w') as f:
            json.dump(data, f)

    def load(self, path: str):
        with open(path, 'r') as f:
            data = json.load(f)
        self.vocab = {k: v for k, v in data["vocab"].items()}
        self.id_to_token = {v: k for k, v in self.vocab.items()}
        self.merges = {tuple(k.split('|')): v for k, v in data["merges"].items()}
        self.next_id = data["next_id"]
        self.special_tokens = data["special_tokens"]
