# PDF Outline Extractor - Adobe Hackathon Round 1A

## Approach

A hybrid approach combining embedded Table of Contents (TOC) extraction with advanced heuristic analysis:

### 1. **Embedded TOC Extraction**
- First attempts to extract the document outline from the PDF's embedded Table of Contents
- Provides the most accurate results when available
- Falls back to heuristic methods if TOC is missing or insufficient

### 2. **Heuristic Analysis with Dynamic Clustering**
When embedded TOC is unavailable, the system uses sophisticated heuristics:

- **Title Detection**: Multi-factor scoring system considering font size, position, centering, and content patterns
- **Heading Identification**: Analyzes font properties, positioning, numbering patterns, and text characteristics
- **Dynamic Style Clustering**: Groups headings by visual similarity (font size, style, color) to assign hierarchical levels
- **Smart Filtering**: Excludes bullet points, numbered lists, and paragraph text using pattern recognition

### 3. **Key Features**
- **Multi-language Support**: Works with documents in different languages including Japanese
- **Performance Optimized**: Parallel processing with ThreadPoolExecutor for multiple PDFs

## Libraries Used

- **PyMuPDF (fitz)**: Primary PDF processing library for text extraction and document analysis
- **re**: Regular expressions for pattern matching and text filtering
- **collections.defaultdict**: Efficient data grouping and organization
- **json**: Output formatting and serialization
- **pathlib**: Modern file path handling
- **concurrent.futures**: Parallel processing for improved performance

## Architecture

```
Input PDFs → TOC Extraction → Heuristic Analysis → Dynamic Clustering → JSON Output
     ↓              ↓               ↓                    ↓              ↓
   /app/input   Embedded TOC    Font Analysis      Level Assignment  /app/output
```

## Docker Requirements Met

- **Platform**: Compatible with AMD64 architecture (linux/amd64)
- **CPU Only**: No GPU dependencies
- **Offline**: No network/internet calls
- **Model Size**: Under 200MB (no ML models used)
- **Performance**: Processes 50-page PDFs in under 10 seconds

## Build and Run

### Build the Docker Image
```bash
docker build --platform linux/amd64 -t pdf-outline-extractor:latest .
```

### Run the Container
```bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none pdf-outline-extractor:latest
```

## Input/Output Format

### Input
- PDF files placed in `/app/input` directory

### Output
- JSON files generated in `/app/output` directory
- One JSON file per input PDF with matching filename

### Output Schema
```json
{
  "title": "Document Title",
  "outline": [
    { "level": "H1", "text": "Chapter 1: Introduction", "page": 1 },
    { "level": "H2", "text": "Background", "page": 2 },
    { "level": "H3", "text": "Research Objectives", "page": 3 }
  ]
}
```


## File Structure

```
.
├── Dockerfile
├── README.md
├── process_pdfs.py          # Entry point and PDF processing orchestration
├── utils.py         # Core extraction and analysis utilities
└── requirements.txt # Dependencies
```

