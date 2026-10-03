from ollama import chat, show
import subprocess
import psutil
import sys

class ModelManager:
    def __init__(self, agent_model: str, judge_model: str):
        self._active_session = False
        self.agent_model = agent_model
        self.judge_model = judge_model
        self._loaded_models = []

    def set_agent(self, model: str):
        if self._active_session:
            raise RuntimeError("Cannot change model during an active session")

        self.agent_model = model

    def set_judge(self, model: str):
        if self._active_session:
            raise RuntimeError("Cannot change model during an active session")

        self.judge_model = model

    def start_session(self):
        if self._active_session:
            raise RuntimeError("A session is already active")

        self.load()
        self._active_session = True

    def stop_session(self):
        if not self._active_session:
            raise RuntimeError("No active session")

        self._active_session = False
        self.unload()

    def load(self):
        if self._active_session:
            raise RuntimeError(
                "Cannot load models during an active session"
            )

        if self._loaded_models:
            raise RuntimeError(
                "Previously loaded models still need cleanup. "
                "Call unload() before loading again."
            )

        models = list(dict.fromkeys([
            self.agent_model,
            self.judge_model,
        ]))

        try:
            for model in models:
                if not self.can_load(model):
                    raise RuntimeError(
                        f"Not enough resources for model: {model}"
                    )

                self._loaded_models.append(model)

                chat(
                    model=model,
                    messages=[],
                    keep_alive=-1,
                )

        except Exception:
            try:
                self.unload()
            except Exception as cleanup_error:
                print(
                    "Cleanup warning after model loading failed: "
                    f"{cleanup_error}",
                    file=sys.stderr,
                )

            raise

    def unload(self):
        if self._active_session:
            raise RuntimeError(
                "Cannot unload models during an active session"
            )

        failures = []

        for model in list(self._loaded_models):
            try:
                chat(
                    model=model,
                    messages=[],
                    keep_alive=0,
                )
            except Exception as error:
                failures.append(
                    f"{model}: {type(error).__name__}: {error}"
                )
            else:
                self._loaded_models.remove(model)

        if failures:
            raise RuntimeError(
                "Some models could not be unloaded:\n"
                + "\n".join(failures)
            )

    def check_resources(self):
        memory = psutil.virtual_memory()

        resources = {
            "ram_total": memory.total,
            "ram_available": memory.available,
            "vram_total": None,
            "vram_available": None
        }

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            total, free = result.stdout.strip().split(",")

            resources["vram_total"] = int(total.strip()) * 1024 * 1024
            resources["vram_available"] = int(free.strip()) * 1024 * 1024

        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            pass

        return resources

    def can_load(self, model: str):
        requirements = self.get_model_requirements(model)
        resources = self.check_resources()

        parameter_count = requirements["parameter_count"]

        if parameter_count is None:
            return False

        estimated_memory = parameter_count * 0.6
        available_memory = resources["ram_available"]

        if resources["vram_available"] is not None:
            available_memory += resources["vram_available"]

        return estimated_memory < available_memory

    def get_model_requirements(self, model: str):
        info = show(model)

        return {
            "parameter_size": info.details.parameter_size,
            "quantization": info.details.quantization_level,
            "parameter_count": info.modelinfo.get("general.parameter_count"),
            "context_length": info.modelinfo.get(
                f"{info.details.family}.context_length"
            ),
        }