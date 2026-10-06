from collections.abc import Sequence

from rag.config import MODEL_NAME, MODEL_VERSION


class SentenceTransformerEncoder:
    """CPU encoder using the multilingual E5 model configured for this RAG."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.version = MODEL_VERSION
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Falta sentence-transformers. Instala las dependencias con "
                "'pip install -r requirements-rag.txt'."
            ) from exc

        torch.manual_seed(0)
        self._model = SentenceTransformer(model_name, device="cpu")
        self._model.eval()

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [[float(value) for value in vector] for vector in vectors]
