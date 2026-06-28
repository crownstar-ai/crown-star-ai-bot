# ====================================================================================================
# dataloader.py – Streaming Dataset & DataLoader for CrownStar‑Absolute
# Features:
#   - StreamingTextDataset: line‑by‑line streaming from text files (memory efficient)
#   - IterableJsonlDataset: streaming JSONL (each line is a JSON object)
#   - TokenizedDataset: pre‑tokenized numpy/mmap dataset for fast loading
#   - DynamicBatchSampler: variable batch sizes (by token count)
#   - Collator: dynamic padding, attention masks, label masking
#   - Supports distributed training (sharding across workers)
# ====================================================================================================

import torch
from torch.utils.data import Dataset, IterableDataset, DataLoader, get_worker_info
import numpy as np
import glob
import json
import linecache
import random
from pathlib import Path
from typing import List, Dict, Iterator, Optional, Tuple, Union, Callable
import logging
import mmap
import os

logger = logging.getLogger("CrownStar.DataLoader")

# ====================================================================================================
# 1. Streaming Text Dataset (line‑by‑line from multiple files)
# ====================================================================================================

class StreamingTextDataset(IterableDataset):
    """
    Memory‑efficient streaming dataset for large text corpora.
    Reads files line by line, tokenises on the fly, and yields (input_ids, labels) pairs.
    Automatically shards across workers for distributed training.
    """
    
    def __init__(self, 
                 file_patterns: List[str], 
                 tokenizer,
                 max_length: int = 1024,
                 shuffle: bool = True,
                 shuffle_buffer_size: int = 10000,
                 seed: int = 42):
        """
        Args:
            file_patterns: List of glob patterns (e.g. ["data/train/*.txt", "data/books/*.txt"])
            tokenizer: BPETokenizer instance.
            max_length: Maximum sequence length (will truncate longer texts).
            shuffle: If True, shuffle files and lines within shuffle buffer.
            shuffle_buffer_size: Number of lines to buffer for shuffling.
            seed: Random seed for reproducibility.
        """
        super().__init__()
        self.file_patterns = file_patterns
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.shuffle = shuffle
        self.shuffle_buffer_size = shuffle_buffer_size
        self.seed = seed
        
        # Collect all file paths
        self.files = []
        for pattern in file_patterns:
            self.files.extend(glob.glob(pattern, recursive=True))
        if not self.files:
            raise ValueError(f"No files found matching patterns: {file_patterns}")
        
        logger.info(f"StreamingTextDataset: {len(self.files)} files, max_length={max_length}")
    
    def _shard_files(self):
        """Distribute files among workers (for distributed training)."""
        worker_info = get_worker_info()
        if worker_info is None:
            return self.files
        else:
            per_worker = len(self.files) // worker_info.num_workers
            start = worker_info.id * per_worker
            end = start + per_worker if worker_info.id < worker_info.num_workers - 1 else len(self.files)
            return self.files[start:end]
    
    def __iter__(self) -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
        worker_files = self._shard_files()
        
        # Optionally shuffle files
        if self.shuffle:
            rng = random.Random(self.seed)
            rng.shuffle(worker_files)
        
        buffer = []
        for filepath in worker_files:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Tokenise the line
                    token_ids = self.tokenizer.encode(line, add_special_tokens=False)
                    if len(token_ids) == 0:
                        continue
                    
                    # Chunk into max_length segments
                    for i in range(0, len(token_ids), self.max_length):
                        chunk = token_ids[i:i+self.max_length]
                        if len(chunk) < 2:
                            continue
                        input_ids = chunk[:-1]
                        labels = chunk[1:]
                        
                        if self.shuffle:
                            buffer.append((input_ids, labels))
                            if len(buffer) >= self.shuffle_buffer_size:
                                random.shuffle(buffer)
                                for inp, lbl in buffer:
                                    yield (torch.tensor(inp, dtype=torch.long), 
                                           torch.tensor(lbl, dtype=torch.long))
                                buffer.clear()
                        else:
                            yield (torch.tensor(input_ids, dtype=torch.long),
                                   torch.tensor(labels, dtype=torch.long))
            
            # Yield remaining buffer after file
            if buffer:
                random.shuffle(buffer)
                for inp, lbl in buffer:
                    yield (torch.tensor(inp, dtype=torch.long),
                           torch.tensor(lbl, dtype=torch.long))
                buffer.clear()
    
    def __len__(self):
        # Approximate length (for progress bars) – can be estimated from total file sizes
        total_chars = 0
        for f in self.files[:100]:  # sample first 100 files
            try:
                total_chars += os.path.getsize(f)
            except:
                pass
        # Rough estimate: ~4 chars per token, max_length tokens per sample
        est_samples = total_chars // (4 * self.max_length) * len(self.files)
        return max(1000, est_samples)


# ====================================================================================================
# 2. Iterable JSONL Dataset (streaming JSON lines)
# ====================================================================================================

class IterableJsonlDataset(IterableDataset):
    """
    Streaming dataset for JSONL files where each line is a JSON object.
    Expects a field name specified by 'text_field'.
    """
    def __init__(self, 
                 file_patterns: List[str],
                 tokenizer,
                 text_field: str = "text",
                 max_length: int = 1024,
                 shuffle: bool = True,
                 seed: int = 42):
        super().__init__()
        self.file_patterns = file_patterns
        self.tokenizer = tokenizer
        self.text_field = text_field
        self.max_length = max_length
        self.shuffle = shuffle
        self.seed = seed
        
        self.files = []
        for pattern in file_patterns:
            self.files.extend(glob.glob(pattern, recursive=True))
        if not self.files:
            raise ValueError(f"No JSONL files found matching patterns: {file_patterns}")
        
        logger.info(f"IterableJsonlDataset: {len(self.files)} files, max_length={max_length}")
    
    def _shard_files(self):
        worker_info = get_worker_info()
        if worker_info is None:
            return self.files
        per_worker = len(self.files) // worker_info.num_workers
        start = worker_info.id * per_worker
        end = start + per_worker if worker_info.id < worker_info.num_workers - 1 else len(self.files)
        return self.files[start:end]
    
    def __iter__(self) -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
        worker_files = self._shard_files()
        if self.shuffle:
            rng = random.Random(self.seed)
            rng.shuffle(worker_files)
        
        for filepath in worker_files:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        text = data.get(self.text_field, "")
                        if not text:
                            continue
                        token_ids = self.tokenizer.encode(text, add_special_tokens=False)
                        for i in range(0, len(token_ids), self.max_length):
                            chunk = token_ids[i:i+self.max_length]
                            if len(chunk) < 2:
                                continue
                            input_ids = chunk[:-1]
                            labels = chunk[1:]
                            yield (torch.tensor(input_ids, dtype=torch.long),
                                   torch.tensor(labels, dtype=torch.long))
                    except json.JSONDecodeError:
                        continue


# ====================================================================================================
# 3. Tokenized Dataset (pre‑tokenised numpy/mmap for speed)
# ====================================================================================================

class TokenizedDataset(Dataset):
    """
    Dataset that loads pre‑tokenised data from numpy files or memory‑mapped arrays.
    Extremely fast for repeated epochs.
    """
    def __init__(self, 
                 data_path: str,
                 max_length: int = 1024,
                 context_length: int = 1024,
                 shuffle: bool = True):
        """
        Args:
            data_path: Path to .npy or .bin file containing token IDs (uint16 or int32).
            max_length: Maximum sequence length for chunking.
            context_length: Length of each training segment (usually = max_length).
            shuffle: Shuffle indices.
        """
        super().__init__()
        self.max_length = max_length
        self.context_length = context_length
        self.shuffle = shuffle
        
        # Load token array
        if data_path.endswith('.npy'):
            self.tokens = np.load(data_path, mmap_mode='r' if os.path.getsize(data_path) > 1e9 else None)
        else:
            # Binary file (uint16)
            self.tokens = np.memmap(data_path, dtype=np.uint16, mode='r')
        
        # Number of possible sequences
        self.num_sequences = max(0, (len(self.tokens) - self.context_length) // self.context_length)
        logger.info(f"TokenizedDataset: {self.num_sequences} sequences of length {self.context_length}")
        
        # Indices for shuffling
        self.indices = list(range(self.num_sequences))
        if self.shuffle:
            random.shuffle(self.indices)
    
    def __len__(self):
        return self.num_sequences
    
    def __getitem__(self, idx):
        if self.shuffle:
            idx = self.indices[idx]
        start = idx * self.context_length
        end = start + self.context_length + 1
        chunk = self.tokens[start:end]
        if len(chunk) < 2:
            # Fallback
            input_ids = torch.zeros(self.context_length, dtype=torch.long)
            labels = torch.zeros(self.context_length, dtype=torch.long)
        else:
            input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
            labels = torch.tensor(chunk[1:], dtype=torch.long)
        return input_ids, labels


# ====================================================================================================
# 4. Dynamic Batch Sampler (batch by total tokens, not fixed count)
# ====================================================================================================

class DynamicBatchSampler:
    """
    Groups sequences into batches based on total token count (not fixed batch size).
    Useful for variable length sequences: batches have similar total tokens.
    """
    def __init__(self, dataset, max_tokens: int = 4096, max_seq_len: int = 1024, shuffle: bool = True):
        self.dataset = dataset
        self.max_tokens = max_tokens
        self.max_seq_len = max_seq_len
        self.shuffle = shuffle
    
    def __iter__(self):
        indices = list(range(len(self.dataset)))
        if self.shuffle:
            random.shuffle(indices)
        
        batch = []
        batch_tokens = 0
        for idx in indices:
            # Estimate tokens (use max_seq_len as proxy; in practice could get actual length)
            seq_len = min(self.max_seq_len, 1024)
            if batch_tokens + seq_len > self.max_tokens and len(batch) > 0:
                yield batch
                batch = []
                batch_tokens = 0
            batch.append(idx)
            batch_tokens += seq_len
        if batch:
            yield batch
    
    def __len__(self):
        # Rough estimate
        return (len(self.dataset) * self.max_seq_len) // self.max_tokens + 1


# ====================================================================================================
# 5. Collator – Dynamic Padding, Attention Masks, Label Masking
# ====================================================================================================

class Collator:
    """
    Collate a batch of variable‑length sequences into padded tensors.
    Also creates attention masks and masks padding tokens in labels (-100).
    """
    def __init__(self, pad_token_id: int = 0, ignore_index: int = -100):
        self.pad_token_id = pad_token_id
        self.ignore_index = ignore_index
    
    def __call__(self, batch: List[Tuple[torch.Tensor, torch.Tensor]]) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            batch: List of (input_ids, labels) tensors of varying lengths.
        Returns:
            input_ids: (batch_size, max_len) padded
            attention_mask: (batch_size, max_len) 1 for real tokens, 0 for padding
            labels: (batch_size, max_len) with ignore_index for padding positions
        """
        input_ids_list = [item[0] for item in batch]
        labels_list = [item[1] for item in batch]
        
        # Determine max length
        max_len = max(t.size(0) for t in input_ids_list)
        
        # Pad input_ids
        padded_inputs = torch.full((len(batch), max_len), self.pad_token_id, dtype=torch.long)
        attention_mask = torch.zeros((len(batch), max_len), dtype=torch.long)
        for i, t in enumerate(input_ids_list):
            padded_inputs[i, :t.size(0)] = t
            attention_mask[i, :t.size(0)] = 1
        
        # Pad labels with ignore_index
        padded_labels = torch.full((len(batch), max_len), self.ignore_index, dtype=torch.long)
        for i, t in enumerate(labels_list):
            padded_labels[i, :t.size(0)] = t
        
        return padded_inputs, attention_mask, padded_labels


# ====================================================================================================
# 6. DataLoader Factory Functions
# ====================================================================================================

def create_streaming_dataloader(
    file_patterns: List[str],
    tokenizer,
    batch_size: int = 8,
    max_length: int = 1024,
    shuffle: bool = True,
    num_workers: int = 2,
    prefetch_factor: int = 2,
    pin_memory: bool = True
) -> DataLoader:
    """
    Create a DataLoader for streaming text files (most memory efficient).
    """
    dataset = StreamingTextDataset(
        file_patterns=file_patterns,
        tokenizer=tokenizer,
        max_length=max_length,
        shuffle=shuffle
    )
    collator = Collator(pad_token_id=tokenizer.special_tokens["<pad>"], ignore_index=-100)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        collate_fn=collator,
        num_workers=num_workers,
        prefetch_factor=prefetch_factor,
        pin_memory=pin_memory
    )


def create_jsonl_dataloader(
    file_patterns: List[str],
    tokenizer,
    batch_size: int = 8,
    max_length: int = 1024,
    text_field: str = "text",
    num_workers: int = 2,
    shuffle: bool = True
) -> DataLoader:
    """
    Create a DataLoader for JSONL files.
    """
    dataset = IterableJsonlDataset(
        file_patterns=file_patterns,
        tokenizer=tokenizer,
        text_field=text_field,
        max_length=max_length,
        shuffle=shuffle
    )
    collator = Collator(pad_token_id=tokenizer.special_tokens["<pad>"], ignore_index=-100)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        collate_fn=collator,
        num_workers=num_workers
    )


def create_tokenized_dataloader(
    data_path: str,
    batch_size: int = 8,
    max_length: int = 1024,
    shuffle: bool = True,
    num_workers: int = 2,
    pin_memory: bool = True
) -> DataLoader:
    """
    Create a DataLoader for pre‑tokenised numpy/mmap files (fastest).
    """
    dataset = TokenizedDataset(
        data_path=data_path,
        max_length=max_length,
        context_length=max_length,
        shuffle=shuffle
    )
    collator = Collator(pad_token_id=0, ignore_index=-100)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        collate_fn=collator,
        num_workers=num_workers,
        shuffle=False,  # already shuffled in dataset
        pin_memory=pin_memory
    )


# ====================================================================================================
# 7. Integration with CrownStarCore (replace old dataloader references)
# ====================================================================================================

def get_train_dataloader(tokenizer, config, data_dir: str = "data/train") -> DataLoader:
    """
    Convenience function to create the default training dataloader.
    """
    file_patterns = [f"{data_dir}/*.txt", f"{data_dir}/**/*.txt"]
    return create_streaming_dataloader(
        file_patterns=file_patterns,
        tokenizer=tokenizer,
        batch_size=config.batch_size,
        max_length=config.max_seq_len,
        shuffle=True,
        num_workers=2
    )


# ====================================================================================================
# Example usage
# ====================================================================================================
"""
from tokenizer import BPETokenizer

tokenizer = BPETokenizer.load("data/tokenizer.json")

# Streaming from text files
loader = create_streaming_dataloader(["data/train/*.txt"], tokenizer, batch_size=4)
for input_ids, attn_mask, labels in loader:
    # Training step
    pass

# JSONL
loader = create_jsonl_dataloader(["data/train.jsonl"], tokenizer, batch_size=4, text_field="content")

# Pre‑tokenised
loader = create_tokenized_dataloader("data/tokens.bin", batch_size=8)

# Dynamic batching
from torch.utils.data import DataLoader
dataset = StreamingTextDataset(["data/train/*.txt"], tokenizer)
sampler = DynamicBatchSampler(dataset, max_tokens=4096)
loader = DataLoader(dataset, batch_sampler=sampler, collate_fn=Collator())
"""

# ====================================================================================================
# END OF dataloader.py (34,128 characters)
# ====================================================================================================
# Append alias for backwards compatibility
import sys, os
sys.path.insert(0, os.path.dirname(__file__) + "/..")
from core.dataloader import create_streaming_dataloader
create_dataloader = create_streaming_dataloader
