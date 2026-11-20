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


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a markdown table without requiring tabulate."""
    cols = [str(c) for c in df.columns.tolist()]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        lines.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(lines)


def _build_tabular_summary(df: pd.DataFrame, label: str) -> str:
    """Pre-compute exact deterministic statistics (totals, min/max rows, group-by sums) so LLMs never miscalculate."""
    if df.empty:
        return ""

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    cat_cols = [c for c in df.columns.tolist() if c not in numeric_cols]
    lines = [f"Computed Summary Statistics ({label}, {len(df)} rows):"]

    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        total = series.sum()
        mean = series.mean()
        max_idx = series.idxmax()
        min_idx = series.idxmin()
        max_row = ", ".join(f"{c}={df.loc[max_idx, c]}" for c in df.columns)
        min_row = ", ".join(f"{c}={df.loc[min_idx, c]}" for c in df.columns)
        lines.append(
            f"- {col}: total={total:g}, average={mean:.2f}, max={series.max():g} ({max_row}), min={series.min():g} ({min_row})"
        )

        # Group-by totals for low-cardinality categorical columns (e.g. region, plan, department)
        for cat in cat_cols[:3]:
            nunique = df[cat].nunique(dropna=True)
            if 1 < nunique <= 15:
                grouped = df.groupby(cat, dropna=True)[col].sum().sort_values(ascending=False)
                breakdown = ", ".join(f"{k}={v:g}" for k, v in grouped.items())
                lines.append(f"  - {col} by {cat}: {breakdown}")

    return "\n".join(lines)


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

        # Create chunks from rows with exact pre-computed statistics
        summary_text = _build_tabular_summary(df, sheet_name)
        sheet_text = f"Sheet: {sheet_name}\n"
        if summary_text:
            sheet_text += summary_text + "\n\n"
        sheet_text += _df_to_markdown(df)

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

    summary_text = _build_tabular_summary(df, 'CSV')
    csv_text = (summary_text + "\n\n" if summary_text else "") + _df_to_markdown(df)
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


def parse_txt(filepath: str) -> Dict[str, Any]:
    """Parse plain text file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    chunks = []
    if text.strip():
        for chunk_text_content in chunk_text(text):
            chunks.append({
                'content': chunk_text_content,
                'token_count': count_tokens(chunk_text_content),
                'page_number': 1,
                'metadata': {'source': 'txt'},
            })

    return {
        'chunks': chunks,
        'page_count': 1,
        'sheet_names': [],
        'column_info': {},
    }