import os
import json
from pathlib import Path
from utils import *
from concurrent.futures import ThreadPoolExecutor

def pdf_processor(pdf_file):
    try:
        doc = fitz.open(pdf_file)
    except Exception as e:
        print(json.dumps({"error": f"Could not open PDF file at {pdf_file}: {e}"}, indent=2))
        sys.exit(1)

    # Try TOC first, then fallback to heuristic with dynamic clustering
    result = build_outline_from_toc(doc)
    if not result or not result.get("outline"):
        result = build_outline_heuristic(doc)
    output_filename = Path(pdf_file).with_suffix('.json').name
    output_filepath = Path("/app/output")
    print("DUMPING")
    # Write the resulting dictionary to the JSON file
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return result

def process_pdfs():
    # Get input and output directories
    input_dir = Path("/app/input")
    output_dir = Path("/app/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_files = list(input_dir.glob("*.pdf"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(pdf_processor, pdf_files))
    # print("All processing complete.")
    # print("Results:", results)

if __name__ == "__main__":
    print("Starting processing pdfs")
    process_pdfs() 
    print("completed processing pdfs")
