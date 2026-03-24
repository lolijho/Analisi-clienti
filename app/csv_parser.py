import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation


COLUMN_ALIASES = {
    "data_pagamento": [
        "data", "data pagamento", "data_pagamento", "data operazione",
        "data_operazione", "data valuta", "data_valuta", "date", "payment_date",
    ],
    "importo": [
        "importo", "ammontare", "amount", "valore", "somma", "totale",
        "importo_eur", "importo eur", "dare/avere",
    ],
    "banca": [
        "banca", "bank", "istituto", "istituto bancario", "nome banca",
    ],
    "descrizione": [
        "descrizione", "description", "causale", "motivo", "note", "dettaglio",
        "descrizione operazione",
    ],
    "riferimento": [
        "riferimento", "reference", "ref", "numero", "id transazione",
        "id_transazione", "cro", "trn",
    ],
    "tipo_pagamento": [
        "tipo", "type", "tipo pagamento", "tipo_pagamento", "modalita",
        "metodo", "metodo pagamento",
    ],
    "cliente": [
        "cliente", "client", "beneficiario", "ordinante", "controparte",
        "nome", "ragione sociale", "intestatario",
    ],
}


def detect_delimiter(sample: str) -> str:
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        if sample.count(";") > sample.count(","):
            return ";"
        return ","


def parse_italian_decimal(value: str) -> Decimal:
    if not value:
        return Decimal("0")
    value = value.strip().replace("\u20ac", "").replace(" ", "")
    value = value.lstrip("+")
    if re.match(r"^-?\d{1,3}(\.\d{3})*(,\d{1,2})?$", value):
        value = value.replace(".", "").replace(",", ".")
    elif "," in value and "." not in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")


def parse_date(value: str) -> datetime:
    if not value:
        return None
    value = value.strip()
    formats = [
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d",
        "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def auto_map_columns(headers: list[str]) -> dict:
    mapping = {}
    normalized_headers = [h.strip().lower() for h in headers]
    for field, aliases in COLUMN_ALIASES.items():
        for i, header in enumerate(normalized_headers):
            if header in aliases:
                mapping[field] = i
                break
    return mapping


def preview_csv(file_content: str, max_rows: int = 10) -> dict:
    delimiter = detect_delimiter(file_content[:2000])
    reader = csv.reader(io.StringIO(file_content), delimiter=delimiter)
    rows = []
    headers = []
    for i, row in enumerate(reader):
        if i == 0:
            headers = [h.strip() for h in row]
            continue
        if i > max_rows:
            break
        rows.append(row)
    auto_mapping = auto_map_columns(headers)
    return {
        "headers": headers,
        "rows": rows,
        "delimiter": delimiter,
        "auto_mapping": auto_mapping,
        "total_preview_rows": len(rows),
    }


def parse_csv(file_content: str, column_mapping: dict) -> list[dict]:
    delimiter = detect_delimiter(file_content[:2000])
    reader = csv.reader(io.StringIO(file_content), delimiter=delimiter)
    payments = []
    headers = None
    for i, row in enumerate(reader):
        if i == 0:
            headers = row
            continue
        if not any(cell.strip() for cell in row):
            continue
        payment = {}
        for field, col_idx in column_mapping.items():
            col_idx = int(col_idx)
            if col_idx < 0 or col_idx >= len(row):
                continue
            value = row[col_idx].strip()
            if field == "data_pagamento":
                payment[field] = parse_date(value)
            elif field == "importo":
                payment[field] = parse_italian_decimal(value)
            else:
                payment[field] = value if value else None
        if payment.get("data_pagamento") and payment.get("importo") is not None:
            payments.append(payment)
    return payments
