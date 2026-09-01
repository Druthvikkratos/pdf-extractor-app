import re
import pdfplumber


def extract_novel_pdf(pdf_path):
    """Extract fields from a single Novel-format PDF. Returns a dict."""
    data = {
        "Invoice Number": "", "Invoice Date": "", "GSTIN/ISD": "",
        "Narration": "", "Total": "", "IGST Total": "",
        "CGST Total": "", "SGST Total": "", "Invoice Total": "",
    }

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        inv_no_match = re.search(r"Invoice\s*No[:\.\-]?\s*([A-Za-z0-9\-/]+)", full_text, re.IGNORECASE)
        if inv_no_match:
            data["Invoice Number"] = inv_no_match.group(1).strip()

        inv_date_match = re.search(r"Invoice\s*Date[:\.\-]?\s*(\d{1,2}[.\/-]\d{1,2}[.\/-]\d{2,4})",
                                    full_text, re.IGNORECASE)
        if inv_date_match:
            data["Invoice Date"] = inv_date_match.group(1).strip()

        gstin_match = re.search(r"GSTIN[/\\]ISD\s*[:\-]?\s*([A-Za-z0-9]+)", full_text, re.IGNORECASE)
        if gstin_match:
            data["GSTIN/ISD"] = gstin_match.group(1).strip()

        total_match = re.search(r'Total\s+([0-9,]+\.\d{2})', full_text)
        if total_match:
            data["Total"] = total_match.group(1).replace(',', '').strip()

        igst_match = re.search(r'IGST\s+Total\s+([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        if igst_match:
            data["IGST Total"] = igst_match.group(1).replace(',', '').strip()

        cgst_match = re.search(r'CGST\s+Total\s+([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        if cgst_match:
            data["CGST Total"] = cgst_match.group(1).replace(',', '').strip()

        sgst_match = re.search(r'SGST\s+Total\s+([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        if sgst_match:
            data["SGST Total"] = sgst_match.group(1).replace(',', '').strip()

        invoice_total_match = re.search(r'Invoice\s+Total\s+([0-9,]+\.\d{2})', full_text, re.IGNORECASE)
        if invoice_total_match:
            data["Invoice Total"] = invoice_total_match.group(1).replace(',', '').strip()

        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if len(table) > 1:
                    header_row = None
                    for i, row in enumerate(table):
                        if any(cell and "Desc of Goods/Services" in str(cell) for cell in row):
                            header_row = i
                            break

                    if header_row is not None:
                        headers = table[header_row]
                        desc_col_index = -1
                        for j, header in enumerate(headers):
                            if header and "Desc of Goods/Services" in str(header):
                                desc_col_index = j
                                break

                        if desc_col_index >= 0:
                            narration_lines = []
                            for row in table[header_row + 1:]:
                                if len(row) > desc_col_index and row[desc_col_index]:
                                    narration_text = str(row[desc_col_index]).strip()
                                    if (narration_text and
                                            narration_text != "Desc of Goods/Services" and
                                            not any(k in narration_text.lower()
                                                    for k in ["s.n", "qty", "unit", "rate", "taxable", "non taxable"])):
                                        narration_lines.append(' '.join(narration_text.split()))

                            if narration_lines:
                                data["Narration"] = ' '.join(narration_lines)
                                break
                if data["Narration"]:
                    break
            if data["Narration"]:
                break

        if not data["Narration"]:
            patterns = [
                r"Post Hardware Rent.*?HSN/SAC CODE:997114.*?For the m/o Sep-25",
                r"Post Hardware Rent.*?For the m/o Sep-25",
                r"Post Hardware Rent"
            ]
            for pattern in patterns:
                narration_match = re.search(pattern, full_text, re.DOTALL)
                if narration_match:
                    data["Narration"] = ' '.join(narration_match.group(0).split())
                    break

    return data


NOVEL_COLUMNS = ["File Name", "Invoice Number", "Invoice Date", "GSTIN/ISD", "Narration",
                  "Total", "IGST Total", "CGST Total", "SGST Total", "Invoice Total"]