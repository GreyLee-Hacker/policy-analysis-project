import os

class Config:
    API_KEY = os.getenv("API_KEY", "your_api_key_here")
    MODEL_ENDPOINTS = {
        "model_1": "http://localhost:8001/model_1",
        "model_2": "http://localhost:8002/model_2",
        "model_3": "http://localhost:8003/model_3",
    }
    LOGGING_CONFIG = {
        "level": "INFO",
        "format": "%(asctime)s - %(levelname)s - %(message)s",
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": "logs/model.log",
                "mode": "a",
            },
            "console": {
                "class": "logging.StreamHandler",
            },
        },
    }
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../../data/output")
    INPUT_DIR = os.path.join(os.path.dirname(__file__), "../../data/input")