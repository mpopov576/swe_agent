class EmbeddingModelManager:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._active_session = False

    def set_model(self, model_name: str):
        if self._active_session:
            raise RuntimeError("Cannot change embedding model during an active session")

        self.model_name = model_name

    def start_session(self):
        if self._active_session:
            raise RuntimeError("Cannot start a session while a session is active")

        self._active_session = True

    def stop_session(self):
        if not self._active_session:
            raise RuntimeError("No active embedding session")

        self._active_session = False

    def get_model(self):
        return self.model_name