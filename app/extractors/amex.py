import re
import pytesseract
from PIL import Image
import pdfplumber
import pypdfium2 as pdfium

def extract_text_with_pdfplumber(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber error: {e}")
    return text


def extract_text_with_ocr(pdf_path):
    text = ""
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        for page in pdf:
            bitmap = page.render(scale=2)
            img = bitmap.to_pil()
            text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        print(f"OCR error: {e}")
    return text


def extract_text_from_pdf(pdf_path):
    text = extract_text_with_pdfplumber(pdf_path)
    if len(text.strip()) < 50:
        text = extract_text_with_ocr(pdf_path)
    return text


def clean_text(text):
    lines = text.split('\n')
    unique_lines = []
    seen = set()
    for line in lines:
        line_clean = line.strip()
        if line_clean and line_clean not in seen:
            seen.add(line_clean)
            unique_lines.append(line)
        elif not line_clean:
            unique_lines.append('')
    text = '\n'.join(unique_lines)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text


def extract_address(text):
    address = {'Address Line 1': '', 'Address Line 2': '', 'Address Line 3': ''}

    addr_pattern = r'ADDRESS\s*LINE\s*(\d+)\s*(.+?)(?=ADDRESS\s*LINE|CITY/|GSTIN|\n\s*\n|$)'
    matches = re.findall(addr_pattern, text, re.IGNORECASE | re.DOTALL)

    if matches:
        for match in matches:
            line_num = int(match[0])
            line_text = match[1].strip()
            if line_num == 1:
                address['Address Line 1'] = line_text
            elif line_num == 2:
                address['Address Line 2'] = line_text
            elif line_num == 3:
                address['Address Line 3'] = line_text
        return address

    payee_pattern = r'PAYEE\s*NAME[^\n]*\n(.*?)(?=GSTIN|CITY|\Z)'
    payee_match = re.search(payee_pattern, text, re.IGNORECASE | re.DOTALL)

    if payee_match:
        address_block = payee_match.group(1).strip()
        lines = [line.strip() for line in address_block.split('\n') if line.strip()]
        filtered_lines = [l for l in lines if not re.search(
            r'CITY|PINCODE|GSTIN|PLACE OF SUPPLY|STATE CODE|MERCHANT NO', l, re.IGNORECASE)]
        if len(filtered_lines) >= 1:
            address['Address Line 1'] = filtered_lines[0]
        if len(filtered_lines) >= 2:
            address['Address Line 2'] = filtered_lines[1]
        if len(filtered_lines) >= 3:
            address['Address Line 3'] = filtered_lines[2]

    return address


def extract_invoice_fields(text):
    text = clean_text(text)

    data = {
        'Invoice Date': '', 'Invoice No': '',
        'Address Line 1': '', 'Address Line 2': '', 'Address Line 3': '',
        'Invoice Period': '', 'Description': '', 'Amount': ''
    }

    date_match = re.search(r'INVOICE\s*DATE\s*(\d{2}/\d{2}/\d{2,4})', text, re.IGNORECASE)
    if date_match:
        data['Invoice Date'] = date_match.group(1).strip()

    inv_match = re.search(r'INVOICE\s*NO\.?\s*([A-Z0-9]+)', text, re.IGNORECASE)
    if inv_match:
        data['Invoice No'] = inv_match.group(1).strip()

    data.update(extract_address(text))

    period_match = re.search(r'INVOICE\s*PERIOD\s*([^\n]+)', text, re.IGNORECASE)
    if period_match:
        data['Invoice Period'] = period_match.group(1).strip()

    desc_match = re.search(r'EXEMPT\s*SERVICE\s*FEE\s*(\d+\.?\d*)', text, re.IGNORECASE)
    if desc_match:
        data['Description'] = 'EXEMPT SERVICE FEE'
        data['Amount'] = desc_match.group(1).strip()
    else:
        alt_match = re.search(r'(EXEMPT\s*SERVICE\s*FEE).*?(\d+\.?\d*)', text, re.IGNORECASE | re.DOTALL)
        if alt_match:
            data['Description'] = alt_match.group(1).strip()
            data['Amount'] = alt_match.group(2).strip()

    for i in range(1, 4):
        key = f'Address Line {i}'
        if data[key]:
            data[key] = re.sub(r'GSTIN.*$', '', data[key], flags=re.IGNORECASE).strip()
            data[key] = re.sub(r'CITY.*$', '', data[key], flags=re.IGNORECASE).strip()
            data[key] = re.sub(r'PINCODE.*$', '', data[key], flags=re.IGNORECASE).strip()

    return data


def extract_amex_pdf(pdf_path):
    """Extract fields from a single Amex PDF. Returns a dict (or raises if unreadable)."""
    text = extract_text_from_pdf(pdf_path)
    if not text or len(text.strip()) < 20:
        raise ValueError("Could not extract sufficient text from this PDF (tried text + OCR).")
    return extract_invoice_fields(text)


AMEX_COLUMNS = ['Filename', 'Invoice Date', 'Invoice No', 'Address Line 1',
                 'Address Line 2', 'Address Line 3', 'Invoice Period',
                 'Description', 'Amount']