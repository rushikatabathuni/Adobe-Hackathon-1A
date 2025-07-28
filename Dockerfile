FROM --platform=linux/amd64 python:3.10

WORKDIR /app


# Install Python dependencies
RUN pip install --no-cache-dir pymupdf

# Copy the processing script
COPY . .

# Run the script
CMD ["python", "process_pdfs.py"] 
