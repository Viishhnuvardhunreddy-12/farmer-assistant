"""Test doubles. Tests never call real APIs."""

import hashlib
import re

import numpy as np
from chromadb import Documents, EmbeddingFunction, Embeddings
from pydantic import BaseModel


class FakeLLM:
    """Returns pre-set outputs per schema type, and records what it was asked."""

    model = "fake-model"

    def __init__(self, outputs: dict[type, BaseModel | Exception]):
        self.outputs = outputs
        self.calls: list[tuple[type, object]] = []

    async def parse(self, system, content, output_type, effort="medium", max_tokens=8000):
        self.calls.append((output_type, content))
        out = self.outputs[output_type]
        if isinstance(out, Exception):
            raise out
        return out


class HashEmbedding(EmbeddingFunction):
    """Bag-of-words hashing embedding: deterministic, offline, good enough for tests."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def name() -> str:
        return "test-hash"

    def __call__(self, input: Documents) -> Embeddings:
        vectors = []
        for doc in input:
            v = np.zeros(256, dtype=np.float32)
            for word in re.findall(r"\w+", doc.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
            norm = np.linalg.norm(v)
            vectors.append(v / norm if norm else v)
        return vectors

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> "HashEmbedding":
        return HashEmbedding()
