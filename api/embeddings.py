"""
Semantic embedding utilities using sentence-transformers.
Model: all-MiniLM-L6-v2 (lazy-loaded on first call).
"""
from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_model: "SentenceTransformer | None" = None
MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str) -> bytes:
    """Embed text and return as raw float32 bytes."""
    model = _get_model()
    vec: np.ndarray = model.encode(text, normalize_embeddings=True)
    return vec.astype(np.float32).tobytes()


def embed_query(text: str) -> np.ndarray:
    """Embed query text and return as numpy float32 array."""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def build_procedure_text(proc: dict) -> str:
    """Concatenate title + symptoms + steps into a single searchable string."""
    title = proc.get("title") or ""

    symptoms = proc.get("symptoms") or "[]"
    if isinstance(symptoms, str):
        try:
            symptoms = json.loads(symptoms)
        except Exception:
            symptoms = [symptoms]
    symptoms_text = " ".join(str(s) for s in symptoms)

    steps = proc.get("steps") or "[]"
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except Exception:
            steps = []
    if steps and isinstance(steps[0], dict):
        steps_text = " ".join(
            s.get("description") or s.get("desc") or "" for s in steps
        )
    else:
        steps_text = " ".join(str(s) for s in steps)

    return f"{title} {symptoms_text} {steps_text}".strip()


def search_procedures(query: str, procedures: list[dict], top_k: int = 10) -> list[dict]:
    """Semantic search over procedures. Returns top_k results with 'score' field."""
    q_vec = embed_query(query)
    scored = []
    for proc in procedures:
        emb_bytes = proc.get("embedding")
        if emb_bytes:
            arr = np.frombuffer(emb_bytes, dtype=np.float32)
            score = cosine_similarity(q_vec, arr)
        else:
            # Fallback: embed on the fly
            text = build_procedure_text(proc)
            arr = embed_query(text)
            score = cosine_similarity(q_vec, arr)
        result = {k: v for k, v in proc.items() if k != "embedding"}
        result["score"] = round(score, 4)
        scored.append(result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
