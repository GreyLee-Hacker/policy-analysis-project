import threading
import json
import os
from src.utils.logging_utils import setup_logging
from src.services.llm_service import call_model
from src.services.storage_service import save_results

class PolicyAnalyzer:
    def __init__(self, model_names, input_data):
        self.model_names = model_names
        self.input_data = input_data
        self.results = {}
        self.lock = threading.Lock()

    def analyze(self, model_name, data):
        result = call_model(model_name, data)
        with self.lock:
            self.results[model_name] = result

    def run_analysis(self):
        threads = []
        for model_name in self.model_names:
            thread = threading.Thread(target=self.analyze, args=(model_name, self.input_data))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def save_results(self, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        for model_name, result in self.results.items():
            output_file = os.path.join(output_dir, f"{model_name}_results.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=4)

def main():
    model_names = ["model_a", "model_b", "model_c"]
    input_data = "Your input data here"  # Replace with actual input data
    output_dir = "path/to/output"  # Replace with actual output directory

    setup_logging()  # Set up logging for the project
    analyzer = PolicyAnalyzer(model_names, input_data)
    analyzer.run_analysis()
    analyzer.save_results(output_dir)

if __name__ == "__main__":
    main()