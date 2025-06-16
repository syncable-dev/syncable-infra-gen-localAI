import subprocess
import sys
import shutil
import time
import requests

class OllamaSetup:
    def __init__(self, required_models=None, host="http://localhost:11434"):
        self.host = host
        self.required_models = required_models or [
            "manutic/nomic-embed-code:7b-Q4_K_M",
            "codestral:22b-v0.1-q2_K"
        ]

    def is_installed(self):
        return shutil.which("ollama") is not None

    def is_running(self):
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def start(self):
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
        except Exception as e:
            print(f"Could not start Ollama: {e}")

    def model_present(self, model_name):
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
            # Model list is just the "short" name, i.e. "codestral", "nomic-embed-code"
            short_name = model_name.split(":")[0]
            return short_name in result.stdout
        except Exception:
            return False

    def download_models(self):
        for model in self.required_models:
            print(f"Checking model {model}...")
            if self.model_present(model):
                print(f"Model {model} already present.")
                continue
            print(f"Pulling model {model}...")
            code = subprocess.call(["ollama", "pull", model])
            if code != 0:
                print(f"Failed to pull model {model}. Please check Ollama setup.")
                sys.exit(1)
        print("All models ready.")

    def setup(self):
        if not self.is_installed():
            print("Ollama is not installed. Please install Ollama from https://ollama.com/download and re-run.")
            sys.exit(1)
        if not self.is_running():
            print("Starting Ollama server...")
            self.start()
            if not self.is_running():
                print("Ollama server did not start. Please run 'ollama serve' manually and retry.")
                sys.exit(1)
        self.download_models()
