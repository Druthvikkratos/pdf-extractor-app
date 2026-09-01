import re
import pdfplumber
import os


def extract_text_from_pdf(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""


def extract_invoice_number(text):
    match = re.search(r'Invoice Number\s*:\s*([A-Z0-9]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_invoice_date(text):
    pattern = r'Invoice Date\s*:\s*(\d{1,2}[- ]?[A-Za-z]{3}[- ]?\d{2,4})'
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_gstin_bill_to(text):
    pattern = r'Details of Receiver.*?GSTIN/UID\s*:\s*([A-Z0-9]+)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    pattern = r'Bill To.*?GSTIN/UID\s*:\s*([A-Z0-9]+)'
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_line_items(text):
    line_items = []
    lines = text.split('\n')

    table_start_idx = -1
    table_end_idx = len(lines)

    for i, line in enumerate(lines):
        if re.search(r'(Description of Goods|HSN|SAC).*?(Qty|Rate|Amount)', line, re.IGNORECASE):
            table_start_idx = i
            break

    if table_start_idx == -1:
        return [{}]

    stop_keywords = [
        'Total', 'Reverse Charge', 'Taxable Amount', 'CGST Amount',
        'SGST Amount', 'IGST Amount', 'Round off', 'Rupees',
        'Authorised Signatory', 'IRN', 'IFSC', 'Bank Name',
        'Remittance', 'Virtual Account', 'UPI ID'
    ]

    for i in range(table_start_idx + 1, len(lines)):
        line = lines[i].strip()
        for keyword in stop_keywords:
            if line.startswith(keyword) and re.search(r'\d+\.?\d*', line):
                table_end_idx = i
                break
        if table_end_idx < len(lines):
            break

    current_item = None

    for i in range(table_start_idx + 1, table_end_idx):
        line = lines[i].strip()
        if not line:
            continue

        hsn_match = re.search(r'\b(\d{6})\b', line)

        if hsn_match:
            if current_item:
                line_items.append(current_item)

            current_item = {
                'Description': '', 'HSN_SAC': '', 'Qty': '', 'UOM': '', 'Rate': '',
                'Taxable_Amount': '', 'CGST_Percent': '', 'CGST_Amount': '',
                'SGST_Percent': '', 'SGST_Amount': '', 'IGST_Percent': '', 'IGST_Amount': ''
            }

            hsn_code = hsn_match.group(1)
            current_item['HSN_SAC'] = hsn_code

            hsn_pos = line.find(hsn_code)
            description = line[:hsn_pos].strip()
            description = re.sub(r'^\d+\s+', '', description)
            current_item['Description'] = description

            after_hsn = line[hsn_pos + 6:].strip()
            all_numbers = re.findall(r'\d+\.?\d*', after_hsn)

            if len(all_numbers) >= 3:
                current_item['Qty'] = all_numbers[0]
                current_item['Rate'] = all_numbers[1]
                current_item['Taxable_Amount'] = all_numbers[2]

                remaining = all_numbers[3:]
                if len(remaining) == 2:
                    current_item['IGST_Percent'] = remaining[0]
                    current_item['IGST_Amount'] = remaining[1]
                elif len(remaining) == 4:
                    current_item['CGST_Percent'] = remaining[0]
                    current_item['CGST_Amount'] = remaining[1]
                    current_item['SGST_Percent'] = remaining[2]
                    current_item['SGST_Amount'] = remaining[3]

        elif current_item:
            if '(Detail as per annexure' in line or '(detail as per annexure' in line.lower():
                continue
            if 'Period' in line or re.search(r'\d{2}/\d{2}/\d{2}', line):
                if current_item['Description']:
                    current_item['Description'] += ' '
                current_item['Description'] += line.strip()
            elif line.startswith('(') and 'annexure' not in line.lower():
                if current_item['Description']:
                    current_item['Description'] += ' '
                current_item['Description'] += line.strip()

    if current_item:
        line_items.append(current_item)

    summary_start = table_end_idx
    summary_end = min(summary_start + 20, len(lines))
    summary_section = '\n'.join(lines[summary_start:summary_end])

    cgst_amount_match = re.search(r'CGST Amount\s+(\d+\.?\d*)', summary_section, re.IGNORECASE)
    sgst_amount_match = re.search(r'SGST Amount\s+(\d+\.?\d*)', summary_section, re.IGNORECASE)
    igst_amount_match = re.search(r'IGST Amount\s+(\d+\.?\d*)', summary_section, re.IGNORECASE)

    if cgst_amount_match:
        cgst_amt = cgst_amount_match.group(1)
        for item in line_items:
            if not item['CGST_Amount'] and item['Taxable_Amount']:
                item['CGST_Amount'] = cgst_amt
    if sgst_amount_match:
        sgst_amt = sgst_amount_match.group(1)
        for item in line_items:
            if not item['SGST_Amount'] and item['Taxable_Amount']:
                item['SGST_Amount'] = sgst_amt
    if igst_amount_match:
        igst_amt = igst_amount_match.group(1)
        for item in line_items:
            if not item['IGST_Amount'] and item['Taxable_Amount']:
                item['IGST_Amount'] = igst_amt

    for item in line_items:
        if item['Taxable_Amount'] and item['Taxable_Amount'].replace('.', '').isdigit():
            taxable = float(item['Taxable_Amount'])
            if item['CGST_Amount'] and not item['CGST_Percent']:
                try:
                    item['CGST_Percent'] = f"{(float(item['CGST_Amount']) * 100) / taxable:.2f}"
                except Exception:
                    pass
            if item['SGST_Amount'] and not item['SGST_Percent']:
                try:
                    item['SGST_Percent'] = f"{(float(item['SGST_Amount']) * 100) / taxable:.2f}"
                except Exception:
                    pass
            if item['IGST_Amount'] and not item['IGST_Percent']:
                try:
                    item['IGST_Percent'] = f"{(float(item['IGST_Amount']) * 100) / taxable:.2f}"
                except Exception:
                    pass

    return line_items if line_items else [{}]


def extract_total_invoice_amount(text):
    match = re.search(r'Total Invoice Amount\s+(\d+\.?\d*)', text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_pinelabs_pdf(pdf_path):
    """Extract all line-item rows from a single Pine Labs PDF. Returns a list of dicts."""
    filename = os.path.basename(pdf_path)
    text = extract_text_from_pdf(pdf_path)

    if not text:
        raise ValueError("No text could be extracted from this PDF.")

    invoice_number = extract_invoice_number(text)
    invoice_date = extract_invoice_date(text)
    gstin_bill_to = extract_gstin_bill_to(text)
    total_amount = extract_total_invoice_amount(text)
    line_items = extract_line_items(text)

    rows = []
    for item in line_items:
        rows.append({
            'Filename': filename,
            'Invoice Number': invoice_number,
            'Invoice Date': invoice_date,
            'GSTIN/UID (Bill To)': gstin_bill_to,
            'Description of Goods/Services': item.get('Description', ''),
            'HSN/SAC': item.get('HSN_SAC', ''),
            'Qty': item.get('Qty', ''),
            'UOM': item.get('UOM', ''),
            'Rate': item.get('Rate', ''),
            'Taxable Amount': item.get('Taxable_Amount', ''),
            'CGST %': item.get('CGST_Percent', ''),
            'CGST Amount': item.get('CGST_Amount', ''),
            'SGST %': item.get('SGST_Percent', ''),
            'SGST Amount': item.get('SGST_Amount', ''),
            'IGST %': item.get('IGST_Percent', ''),
            'IGST Amount': item.get('IGST_Amount', ''),
            'Total Invoice Amount': total_amount
        })

    # Keep only rows that look like genuine line items (matches original filter logic)
    valid_rows = [r for r in rows if re.match(r'^\d{6,8}$', str(r['HSN/SAC']))
                  and str(r['Taxable Amount']).replace('.', '').isdigit()]

    return valid_rows if valid_rows else rows


PINELABS_COLUMNS = ['Filename', 'Invoice Number', 'Invoice Date', 'GSTIN/UID (Bill To)',
                     'Description of Goods/Services', 'HSN/SAC', 'Qty', 'UOM', 'Rate',
                     'Taxable Amount', 'CGST %', 'CGST Amount', 'SGST %', 'SGST Amount',
                     'IGST %', 'IGST Amount', 'Total Invoice Amount']