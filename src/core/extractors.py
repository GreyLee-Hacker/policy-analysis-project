from concurrent.futures import ThreadPoolExecutor
import json
import os
import logging
from src.utils.logging_utils import setup_logger
from src.utils.file_utils import write_json
from src.core.models import PolicyDocument

# Set up logging
logger = setup_logger("extractors")

def extract_information_from_document(doc: PolicyDocument):
    # Placeholder for extraction logic
    extracted_data = {
        "doc_id": doc.id,
        "content": doc.content,
        "extracted_info": "Sample extracted information"  # Replace with actual extraction logic
    }
    logger.info(f"Extracted information from document ID: {doc.id}")
    return extracted_data

def process_documents(documents):
    results = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(extract_information_from_document, doc): doc for doc in documents}
        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing document {futures[future].id}: {e}")
    return results

def save_extraction_results(results, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for result in results:
        output_file = os.path.join(output_dir, f"{result['doc_id']}.json")
        write_json(output_file, result)
        logger.info(f"Saved extraction result to {output_file}")