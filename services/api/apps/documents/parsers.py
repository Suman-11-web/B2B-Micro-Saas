"""
Document parsers for PDF, Excel, and CSV files.
"""
import pdfplumber
import pandas as pd
from openpyxl import load_workbook
from typing import List, Dict, Any
import tiktoken


# Tokenizer for chunk sizing
enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text."""
    return len(enc.encode(text))


def chunk_text(text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks by token count."""
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        if end == len(tokens):
            break
        start = end - overlap
    return chunks


def parse_pdf(filepath: str) -> Dict[str, Any]:
    """Parse PDF file and extract text with page info."""
    chunks = []
    page_count = 0
    all_text = ""

    with pdfplumber.open(filepath) as pdf:
        page_count = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            tables = page.extract_tables()

            # Add table content as markdown
            for table in tables:
                if table:
                    text += "\n\nTable:\n"
                    for row in table:
                        text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"

            if text.strip():
                page_chunks = chunk_text(text)
                for chunk_text_content in page_chunks:
                    chunks.append({
                        'content': chunk_text_content,
                        'token_count': count_tokens(chunk_text_content),
                        'page_number': page_num,
                        'metadata': {'source': 'pdf', 'page': page_num}
                    })
                all_text += text + "\n"

    return {
        'chunks': chunks,
        'page_count': page_count,
        'sheet_names': [],
        'column_info': {},
    }


def parse_excel(filepath: str) -> Dict[str, Any]:
    """Parse Excel file and extract data from each sheet."""
    chunks = []
    sheet_names = []
    column_info = {}

    wb = load_workbook(filepath, read_only=True, data_only=True)
    sheet_names = wb.sheetnames

    for sheet_name in sheet_names:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            continue

        # First row as headers
        headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows[0])]
        column_info[sheet_name] = headers

        # Convert to DataFrame for easier processing
        df = pd.DataFrame(rows[1:], columns=headers)

        # Create chunks from rows
        sheet_text = f"Sheet: {sheet_name}\n"
        sheet_text += df.to_markdown(index=False)

        sheet_chunks = chunk_text(sheet_text)
        for i, chunk_text_content in enumerate(sheet_chunks):
            chunks.append({
                'content': chunk_text_content,
                'token_count': count_tokens(chunk_text_content),
                'page_number': None,
                'sheet_name': sheet_name,
                'row_range': {'start': i * 50, 'end': min((i + 1) * 50, len(df))},
                'metadata': {'source': 'excel', 'sheet': sheet_name}
            })

    wb.close()

    return {
        'chunks': chunks,
        'page_count': 0,
        'sheet_names': sheet_names,
        'column_info': column_info,
    }


def parse_csv(filepath: str) -> Dict[str, Any]:
    """Parse CSV file."""
    chunks = []
    column_info = {}

    # Try to detect delimiter
    try:
        df = pd.read_csv(filepath)
    except Exception:
        df = pd.read_csv(filepath, sep=None, engine='python')

    column_info['default'] = df.columns.tolist()
    sheet_names = ['default']

    csv_text = df.to_markdown(index=False)
    csv_chunks = chunk_text(csv_text)

    for i, chunk_text_content in enumerate(csv_chunks):
        chunks.append({
            'content': chunk_text_content,
            'token_count': count_tokens(chunk_text_content),
            'page_number': None,
            'sheet_name': 'default',
            'row_range': {'start': i * 50, 'end': min((i + 1) * 50, len(df))},
            'metadata': {'source': 'csv'}
        })

    return {
        'chunks': chunks,
        'page_count': 0,
        'sheet_names': sheet_names,
        'column_info': column_info,
    }