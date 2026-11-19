"""
Embedding generation using OpenAI API.
"""
import openai
from django.conf import settings
from typing import List
import numpy as np
import structlog

logger = structlog.get_logger()

# Initialize OpenAI client
client = openai.OpenAI(
    api_key=settings.OPENAI_API_KEY,
    organization=settings.OPENAI_ORG_ID or None,
    base_url=settings.OPENAI_BASE_URL,
)


def generate_embeddings(texts: List[str]) -> List[np.ndarray]:
    """Generate embeddings for a list of texts."""
    if not texts:
        return []

    try:
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            encoding_format="float",
        )

        embeddings = []
        for data in response.data:
            embedding = np.array(data.embedding, dtype=np.float32)
            # Normalize for cosine similarity
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)

        logger.info("Embeddings generated", count=len(embeddings), model=settings.EMBEDDING_MODEL)
        return embeddings

    except Exception as e:
        logger.error("Embedding generation failed", error=str(e))
        raise


def generate_single_embedding(text: str) -> np.ndarray:
    """Generate embedding for a single text."""
    return generate_embeddings([text])[0]