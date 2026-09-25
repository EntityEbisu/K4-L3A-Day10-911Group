from __future__ import annotations

import requests
from langchain_core.embeddings import Embeddings

from core.config import Settings

_BATCH_SIZE = 32


class CustomOpenAIEmbeddings(Embeddings):
    """OpenAI-compatible embeddings client for custom LLM endpoints."""

    def __init__(self, settings: Settings):
        if not settings.custom_llm_base_url:
            raise RuntimeError("CUSTOM_LLM_BASE_URL is required for custom embeddings.")
        self.base_url = settings.custom_llm_base_url.rstrip("/")
        self.model = settings.embedding_model
        self.api_key = settings.custom_llm_api_key or "unused"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        url = f"{self.base_url}/embeddings"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            payload = {"model": self.model, "input": batch}
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            if not response.ok:
                raise RuntimeError(
                    f"Embeddings request failed ({response.status_code}) at {url}: {response.text[:500]}"
                )
            data = response.json()
            ordered = sorted(data["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in ordered)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def build_embeddings(settings: Settings) -> CustomOpenAIEmbeddings:
    return CustomOpenAIEmbeddings(settings)


MiniLMEmbeddings = CustomOpenAIEmbeddings
