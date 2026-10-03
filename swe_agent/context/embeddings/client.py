from sentence_transformers import SentenceTransformer

class EmbeddingClient:
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self._model = None
        self._loaded_model_name = None

    def load(self):
        model_name = self.model_manager.get_model()

        if self._loaded_model_name == model_name:
            return

        self._model = SentenceTransformer(model_name)
        self._loaded_model_name = model_name

    def embed(self, texts: list[str]):
        if self._model is None:
            raise RuntimeError("Model not loaded")

        return self._model.encode(
            texts,
            convert_to_numpy=True
        ).tolist()

    def unload(self):
        self._model = None
        self._loaded_model_name = None