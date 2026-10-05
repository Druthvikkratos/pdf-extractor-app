import re
import pdfplumber


def _read_pdf_text(pdf_path):
    """Return the full text of every page joined with newlines."""
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
    return full_text


def _extract_novel_format(pdf_path):
    """Extract fields from a single Novel-format PDF. Returns a dict."""
    data = {
        "Invoice Number": "",
        "Invoice Date": "",
        "GSTIN/ISD": "",
        "Narration": "",
        "Total": "",
        "IGST Total": "",
        "CGST Total": "",
        "SGST Total": "",
        "Invoice Total": "",
    }

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        inv_no_match = re.search(
            r"Invoice\s*No[:\.\-]?\s*([A-Za-z0-9\-/]+)", full_text, re.IGNORECASE
        )
        if inv_no_match:
            data["Invoice Number"] = inv_no_match.group(1).strip()

        inv_date_match = re.search(
            r"Invoice\s*Date[:\.\-]?\s*(\d{1,2}[.\/-]\d{1,2}[.\/-]\d{2,4})",
            full_text,
            re.IGNORECASE,
        )
        if inv_date_match:
            data["Invoice Date"] = inv_date_match.group(1).strip()

        gstin_match = re.search(
            r"GSTIN[/\\]ISD\s*[:\-]?\s*([A-Za-z0-9]+)", full_text, re.IGNORECASE
        )
        if gstin_match:
            data["GSTIN/ISD"] = gstin_match.group(1).strip()

        total_match = re.search(r"Total\s+([0-9,]+\.\d{2})", full_text)
        if total_match:
            data["Total"] = total_match.group(1).replace(",", "").strip()

        igst_match = re.search(
            r"IGST\s+Total\s+([0-9,]+\.\d{2})", full_text, re.IGNORECASE
        )
        if igst_match:
            data["IGST Total"] = igst_match.group(1).replace(",", "").strip()

        cgst_match = re.search(
            r"CGST\s+Total\s+([0-9,]+\.\d{2})", full_text, re.IGNORECASE
        )
        if cgst_match:
            data["CGST Total"] = cgst_match.group(1).replace(",", "").strip()

        sgst_match = re.search(
            r"SGST\s+Total\s+([0-9,]+\.\d{2})", full_text, re.IGNORECASE
        )
        if sgst_match:
            data["SGST Total"] = sgst_match.group(1).replace(",", "").strip()

        invoice_total_match = re.search(
            r"Invoice\s+Total\s+([0-9,]+\.\d{2})", full_text, re.IGNORECASE
        )
        if invoice_total_match:
            data["Invoice Total"] = (
                invoice_total_match.group(1).replace(",", "").strip()
            )

        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if len(table) > 1:
                    header_row = None
                    for i, row in enumerate(table):
                        if any(
                            cell and "Desc of Goods/Services" in str(cell)
                            for cell in row
                        ):
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
                            for row in table[header_row + 1 :]:
                                if len(row) > desc_col_index and row[desc_col_index]:
                                    narration_text = str(row[desc_col_index]).strip()
                                    if (
                                        narration_text
                                        and narration_text != "Desc of Goods/Services"
                                        and not any(
                                            k in narration_text.lower()
                                            for k in [
                                                "s.n",
                                                "qty",
                                                "unit",
                                                "rate",
                                                "taxable",
                                                "non taxable",
                                            ]
                                        )
                                    ):
                                        narration_lines.append(
                                            " ".join(narration_text.split())
                                        )

                            if narration_lines:
                                data["Narration"] = " ".join(narration_lines)
                                break
                if data["Narration"]:
                    break
            if data["Narration"]:
                break

        if not data["Narration"]:
            patterns = [
                r"Post Hardware Rent.*?HSN/SAC CODE:997114.*?For the m/o Sep-25",
                r"Post Hardware Rent.*?For the m/o Sep-25",
                r"Post Hardware Rent",
            ]
            for pattern in patterns:
                narration_match = re.search(pattern, full_text, re.DOTALL)
                if narration_match:
                    data["Narration"] = " ".join(narration_match.group(0).split())
                    break

    return data


def _extract_sangeeta_format(pdf_path):
    data = {
        "Invoice Number": "",
        "Invoice Date": "",
        "GSTIN/ISD": "",
        "Client/Buyer Name": "",
        "Address": "",
        "HSN/SAC Code": "",
        "Narration": "",
        "Total": "",
        "Total Taxable Amount": "",
        "IGST Total": "",
        "CGST Total": "",
        "SGST Total": "",
        "Invoice Total": "",
    }

    # Read ALL pages — CGST/SGST/TOTAL live on page 2
    full_text = _read_pdf_text(pdf_path)

    # Invoice Number
    m = re.search(
        r"Invoice\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-/]+)", full_text, re.IGNORECASE
    )
    if m:
        data["Invoice Number"] = m.group(1).strip()

    # Invoice Date  ("Date: 03- 09- 26" -> "03-09-26")
    m = re.search(
        r"Date\s*[:\-]\s*(\d{1,2}\s*[.\-\/]\s*\d{1,2}\s*[.\-\/]\s*\d{2,4})",
        full_text,
        re.IGNORECASE,
    )
    if m:
        data["Invoice Date"] = re.sub(r"\s+", "", m.group(1))

    # Buyer GSTIN — first valid GSTIN in the PDF (buyer comes before supplier)
    gstins = re.findall(
        r"GSTIN\s*[:\-]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z])", full_text
    )
    if gstins:
        data["GSTIN/ISD"] = gstins[0]

    # Client / Buyer name
    m = re.search(r"(M/s\.\s*[^\n]+)", full_text)
    if m:
        data["Client/Buyer Name"] = m.group(1).strip()

    # Buyer address — anchor on "Unit no." and stop at "GSTIN".
    # Then drop the interleaved right-column noise lines.
    m = re.search(r"(Unit\s*no\..*?)\s*GSTIN", full_text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1)
        kept = []
        for line in raw.split("\n"):
            s = line.strip()
            if not s:
                continue
            # Skip right-column noise
            if re.search(r"P\.?\s*O\.?\s*No", s, re.IGNORECASE):
                continue
            if re.search(r"Place\s+of\s+Supply", s, re.IGNORECASE):
                continue
            if re.fullmatch(r"Date\s*:?\s*", s, re.IGNORECASE):
                continue
            kept.append(s)
        data["Address"] = " ".join(" ".join(kept).split())

    # HSN / SAC code
    m = re.search(r"HSN\s*/?\s*SAC[^\d]*(\d{4,8})", full_text, re.IGNORECASE)
    if not m:
        m = re.search(r"\b(\d{8})\b", full_text)
    if m:
        data["HSN/SAC Code"] = m.group(1)

    # Total Taxable Amount
    m = re.search(
        r"Total\s+Taxable\s+Amount\s*:?\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE
    )
    if m:
        val = m.group(1).replace(",", "").strip()
        data["Total Taxable Amount"] = val
        data["Total"] = val

    # IGST (usually absent in this format)
    m = re.search(r"Add\s*:?\s*IGST\s*:?\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if m:
        data["IGST Total"] = m.group(1).replace(",", "").strip()

    # CGST (page 2)
    m = re.search(r"Add\s*:?\s*CGST\s*:?\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if m:
        data["CGST Total"] = m.group(1).replace(",", "").strip()

    # SGST (page 2)
    m = re.search(r"Add\s*:?\s*SGST\s*:?\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if m:
        data["SGST Total"] = m.group(1).replace(",", "").strip()

    # Grand total (page 2). \bTOTAL\b avoids matching "Total Taxable Amount".
    m = re.search(r"\bTOTAL\b\s*:?\s*([\d,]+\.\d{2})", full_text)
    if m:
        data["Invoice Total"] = m.group(1).replace(",", "").strip()

    for k in [
        "Total",
        "Total Taxable Amount",
        "IGST Total",
        "CGST Total",
        "SGST Total",
        "Invoice Total",
    ]:
        if not str(data.get(k, "")).strip():
            data[k] = "0.00"

    return data


# ===========================================================================
# PUBLIC ENTRY POINT (what main.py imports)
# Auto-detects the vendor and routes to the right extractor.
# ===========================================================================
def extract_novel_pdf(pdf_path):
    """
    Entry point used by main.py.
    - If the PDF text contains 'SANGEETA PRINTING PRESS', use the Sangeeta parser.
    - Otherwise use the original Novel-format parser.
    """
    text = _read_pdf_text(pdf_path).upper()

    if "SANGEETA PRINTING PRESS" in text:
        return _extract_sangeeta_format(pdf_path)

    return _extract_novel_format(pdf_path)


NOVEL_COLUMNS = [
    "File Name",
    "Invoice Number",
    "Invoice Date",
    "GSTIN/ISD",
    "Client/Buyer Name",
    "Address",
    "HSN/SAC Code",
    "Total",
    "Total Taxable Amount",
    "IGST Total",
    "CGST Total",
    "SGST Total",
    "Invoice Total",
]
