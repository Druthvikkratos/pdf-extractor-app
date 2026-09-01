import pdfplumber
import re
from collections import defaultdict


def words_to_lines(words):
    rows = defaultdict(list)
    for w in words:
        rows[round(w['top'])].append(w)
    return [' '.join(w['text'] for w in sorted(rows[k], key=lambda x: x['x0']))
            for k in sorted(rows)]


def parse_recipient(page):
    words = page.extract_words()
    party_recip = [w for w in words if w['text'] == 'Recipient' and w['top'] > 400]
    party_hdr = next((w for w in words if '3.Party' in w['text']), None)
    goods_hdr = next((w for w in words if w['text'] == 'Goods'), None)
    if not party_recip or not party_hdr or not goods_hdr:
        return '', '', '', ''

    recip_x = party_recip[0]['x0']
    y_start = party_hdr['bottom']
    y_end = goods_hdr['top']

    recip_words = [w for w in words
                   if w['x0'] >= recip_x - 5
                   and w['top'] >= y_start
                   and w['bottom'] <= y_end + 20]

    lines = words_to_lines(recip_words)
    gstin = name = place = ''
    addr_parts = []
    found_gstin = False

    for line in lines:
        line = line.strip()
        if not line or 'Recipient' in line:
            continue
        if 'GSTIN' in line:
            m = re.search(r'GSTIN\s*:?\s*(\S+)', line)
            if m:
                gstin = m.group(1)
            found_gstin = True
            continue
        if not found_gstin:
            continue
        if 'Place' in line and 'Supply' in line:
            ps = re.search(r'Supply[:\s]+(\w+)', line)
            if ps:
                place = ps.group(1)
        elif re.match(r'^\d{6}\s+\w+', line):
            pass
        elif not name:
            name = line
        else:
            addr_parts.append(line)

    return gstin, name, ', '.join(addr_parts), place


def clean_row(row):
    return [str(c).strip() for c in row if c is not None and str(c).strip() not in ('', 'None')]


def parse_items_from_table(page):
    items = []
    text = page.extract_text() or ''
    tables = page.extract_tables()

    for table in tables:
        for row in table:
            if not row or row[0] is None:
                continue
            first = str(row[0]).strip()
            if not re.match(r'^\d+$', first):
                continue

            def g(i):
                return str(row[i]).strip() if i < len(row) and row[i] else ''

            desc = re.sub(r'\s+', ' ', g(1))
            hsn = g(4)
            qty = g(6)
            unit = g(8)
            unitprice = g(9)
            discount = g(11)
            taxable = g(13)
            tax_rate = re.sub(r'\s+', ' ', g(15)).strip()

            other_chg = ''
            item_total = ''
            m = re.search(
                re.escape(hsn) + r'\s+' + re.escape(qty) + r'\s+' + re.escape(unit) +
                r'\s+' + re.escape(unitprice) + r'\s+' + re.escape(discount) +
                r'\s+' + re.escape(taxable) + r'\s+[\d.+\s|]+?\s+([\d.]+)\s+([\d.]+)',
                text
            )
            if m:
                other_chg = m.group(1)
                item_total = m.group(2)
            else:
                flat_line = re.search(
                    re.escape(taxable) + r'.*?([\d.+\s|]+?)\s+([\d.]+)\s+([\d.]+)(?:\s|$)',
                    text
                )
                if flat_line:
                    other_chg = flat_line.group(2)
                    item_total = flat_line.group(3)

            items.append({
                'Item Description': desc,
                'HSN Code': hsn,
                'Quantity': qty,
                'Unit': unit,
                'Unit Price(Rs)': unitprice,
                'Discount(Rs)': discount,
                'Taxable Amount(Rs)': taxable,
                'Tax Rate': tax_rate,
                'Other Charges': other_chg,
                'Item Total': item_total,
            })
    return items


def parse_tax_summary(page, text):
    empty = dict(taxable='', cgst='', sgst='', igst='', cess='', state_cess='',
                 discount='', other_charges='', round_off='', total='')
    tables = page.extract_tables()
    for table in tables:
        for i, row in enumerate(table):
            if not row:
                continue
            row_text = ' '.join(str(c) for c in row if c)
            if "Tax'ble Amt" in row_text or "Taxble Amt" in row_text:
                for j in range(i + 1, len(table)):
                    vals = clean_row(table[j])
                    if len(vals) >= 8:
                        last = vals[-1]
                        if ' ' in last:
                            extra = last.split()
                            vals = vals[:-1] + extra
                        if len(vals) >= 10:
                            return dict(
                                taxable=vals[0], cgst=vals[1], sgst=vals[2], igst=vals[3],
                                cess=vals[4], state_cess=vals[5], discount=vals[6],
                                other_charges=vals[7], round_off=vals[8], total=vals[9]
                            )
                        break

    m = re.search(
        r'([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\n',
        text
    )
    if m:
        g = m.groups()
        return dict(taxable=g[0], cgst=g[1], sgst=g[2], igst=g[3], cess=g[4],
                    state_cess=g[5], discount=g[6], other_charges=g[7], round_off=g[8], total=g[9])
    return empty


def extract_airplay_pdf(pdf_path):
    """Extract all records from a single Airplay PDF invoice."""
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''

            doc_no_m = re.search(r'Document No\.\s*:\s*(\S+)', text)
            doc_date_m = re.search(r'Document Date\s*:\s*(\S+)', text)
            doc_no = doc_no_m.group(1) if doc_no_m else ''
            doc_date = doc_date_m.group(1) if doc_date_m else ''

            if not doc_no:
                continue

            sup_m = re.search(r'Supplier\s*:.*?GSTIN\s*:\s*(\S+)', text, re.DOTALL)
            supplier_gstin = sup_m.group(1) if sup_m else ''

            recip_gstin, recip_name, recip_addr, place_of_supply = parse_recipient(page)

            if not place_of_supply:
                ps = re.search(r'Place of Supply\s*:\s*(\w+)', text)
                place_of_supply = ps.group(1) if ps else ''

            items = parse_items_from_table(page)
            tax = parse_tax_summary(page, text)

            for item in items:
                records.append({
                    'Document No.': doc_no,
                    'Document Date': doc_date,
                    'Supplier GSTIN': supplier_gstin,
                    'Recipient GSTIN': recip_gstin,
                    'Recipient Name': recip_name,
                    'Recipient Address': recip_addr,
                    'Place of Supply': place_of_supply,
                    **item,
                    "Tax'ble Amt": tax['taxable'],
                    'CGST Amt': tax['cgst'],
                    'SGST Amt': tax['sgst'],
                    'IGST Amt': tax['igst'],
                    'CESS Amt': tax['cess'],
                    'State CESS': tax['state_cess'],
                    'Discount (Summary)': tax['discount'],
                    'Other Charges (Summary)': tax['other_charges'],
                    'Round off Amt': tax['round_off'],
                    'Total Invoice Amt': tax['total'],
                })

            if not items:
                records.append({
                    'Document No.': doc_no, 'Document Date': doc_date,
                    'Supplier GSTIN': supplier_gstin,
                    'Recipient GSTIN': recip_gstin, 'Recipient Name': recip_name,
                    'Recipient Address': recip_addr, 'Place of Supply': place_of_supply,
                    'Item Description': '', 'HSN Code': '',
                    'Quantity': '', 'Unit': '', 'Unit Price(Rs)': '',
                    'Discount(Rs)': '', 'Taxable Amount(Rs)': '', 'Tax Rate': '',
                    'Other Charges': '', 'Item Total': '',
                    "Tax'ble Amt": tax['taxable'], 'CGST Amt': tax['cgst'],
                    'SGST Amt': tax['sgst'], 'IGST Amt': tax['igst'],
                    'CESS Amt': tax['cess'], 'State CESS': tax['state_cess'],
                    'Discount (Summary)': tax['discount'],
                    'Other Charges (Summary)': tax['other_charges'],
                    'Round off Amt': tax['round_off'], 'Total Invoice Amt': tax['total'],
                })

    return records


AIRPLAY_COLUMNS = [
    'Source File', 'Document No.', 'Document Date',
    'Supplier GSTIN', 'Recipient GSTIN', 'Recipient Name',
    'Recipient Address', 'Place of Supply',
    'Item Description', 'HSN Code', 'Quantity', 'Unit',
    'Unit Price(Rs)', 'Discount(Rs)', 'Taxable Amount(Rs)', 'Tax Rate',
    'Other Charges', 'Item Total',
    "Tax'ble Amt", 'CGST Amt', 'SGST Amt', 'IGST Amt',
    'CESS Amt', 'State CESS', 'Discount (Summary)',
    'Other Charges (Summary)', 'Round off Amt', 'Total Invoice Amt',
]