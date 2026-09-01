import pandas as pd
import os


def build_excel(records, columns, output_path):
    """records: list of dicts. columns: fixed column order. Writes xlsx to output_path."""
    if not records:
        raise ValueError("No data was extracted from the uploaded PDF(s).")

    df = pd.DataFrame(records)

    # Ensure every expected column exists even if some rows are missing it
    for col in columns:
        if col not in df.columns:
            df[col] = ''

    # Keep only known columns, in fixed order (drop anything unexpected)
    df = df[columns]

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    df.to_excel(output_path, index=False, engine='openpyxl')

    return df