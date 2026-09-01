import re
import pypdfium2 as pdfium


def extract_text_from_pdf(pdf_path):
    text = ""
    pdf = pdfium.PdfDocument(pdf_path)
    try:
        for page in pdf:
            textpage = page.get_textpage()
            text += textpage.get_text_range() + "\n"
    finally:
        pdf.close()
    return text


def extract_aerom_pdf(pdf_path):
    """Extract fields from a single Aerom PDF. Returns a dict."""
    import os
    filename = os.path.basename(pdf_path)
    text = extract_text_from_pdf(pdf_path)

    data = {
        'Invoice No.': '', 'Dated': '', 'Terms of Delivery': '',
        'GSTIN/UIN': '', 'Quantity': '', 'Amount': '', 'File Name': filename
    }

    match = re.search(r'Invoice\s+No\.?\s*\n?\s*([A-Za-z0-9/-]+)', text, re.IGNORECASE)
    if match:
        data['Invoice No.'] = match.group(1).strip()

    match = re.search(r'Dated\s*\n?\s*(\d{1,2}-[A-Za-z]{3}-\d{2})', text, re.IGNORECASE)
    if match:
        data['Dated'] = match.group(1).strip()

    match = re.search(r'Terms\s+of\s+Delivery\s*\n?\s*([^\n]+)', text, re.IGNORECASE)
    if match:
        terms = match.group(1).strip()
        if terms:
            data['Terms of Delivery'] = terms

    buyer_match = re.search(r'Buyer\s*\(Bill\s+to\)(.*?)(?:Invoice|Delivery)', text, re.DOTALL | re.IGNORECASE)
    if buyer_match:
        gstin_match = re.search(r'GSTIN/UIN\s*:?\s*([A-Z0-9]{15})', buyer_match.group(1))
        if gstin_match:
            data['GSTIN/UIN'] = gstin_match.group(1).strip()

    match = re.search(r'Total\s+(\d+)\s+Nos', text, re.IGNORECASE)
    if match:
        data['Quantity'] = match.group(1).strip()
    else:
        match = re.search(r'^\s*(\d+)\s+Nos', text, re.MULTILINE)
        if match:
            data['Quantity'] = match.group(1).strip()

    match = re.search(r'Total\s+\d+\s+Nos\s+[ī₹\|]\s*([\d,]+\.?\d{2})', text)
    if match:
        data['Amount'] = match.group(1).strip()
    else:
        match = re.search(r'Total\s+[^\d]*([\d,]+\.\d{2})', text)
        if match:
            data['Amount'] = match.group(1).strip()
        else:
            match = re.search(r'Indian Rupees\s+[A-Za-z\s]+?([\d,]+)\s+Only', text, re.IGNORECASE)
            if match:
                amount_match = re.search(r'([\d,]+\.\d{2})', text[max(0, match.start() - 200):match.start()])
                if amount_match:
                    data['Amount'] = amount_match.group(1).strip()

    return data


AEROM_COLUMNS = ['File Name', 'Invoice No.', 'Dated', 'Terms of Delivery',
                  'GSTIN/UIN', 'Quantity', 'Amount']