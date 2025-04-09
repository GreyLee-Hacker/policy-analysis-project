from pathlib import Path
import json
import os

class StorageService:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_results(self, model_name, results):
        file_path = self.output_dir / f"{model_name}_results.json"
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(results, json_file, ensure_ascii=False, indent=4)

    def log_results(self, model_name, log_data):
        log_file_path = self.output_dir / f"{model_name}_log.json"
        with open(log_file_path, 'w', encoding='utf-8') as log_file:
            json.dump(log_data, log_file, ensure_ascii=False, indent=4)