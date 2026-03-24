from datetime import datetime, date
from decimal import Decimal

from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func, extract

from app import db
from app.models import Payment, CsvUpload
from app.csv_parser import preview_csv, parse_csv, auto_map_columns

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@main_bp.route("/upload")
def upload_page():
    return render_template("upload.html")


@main_bp.route("/payments")
def payments_page():
    return render_template("payments.html")


@main_bp.route("/api/stats")
def api_stats():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    banca = request.args.get("banca")

    query = Payment.query

    if date_from:
        try:
            query = query.filter(
                Payment.data_pagamento >= datetime.strptime(date_from, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                Payment.data_pagamento <= datetime.strptime(date_to, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if banca:
        query = query.filter(Payment.banca == banca)

    totale = query.with_entities(func.sum(Payment.importo)).scalar() or 0
    num_pagamenti = query.count()
    media = float(totale) / num_pagamenti if num_pagamenti > 0 else 0
    importo_max = query.with_entities(func.max(Payment.importo)).scalar() or 0
    importo_min = query.with_entities(func.min(Payment.importo)).scalar() or 0

    monthly = (
        query.with_entities(
            extract("year", Payment.data_pagamento).label("anno"),
            extract("month", Payment.data_pagamento).label("mese"),
            func.sum(Payment.importo).label("totale"),
            func.count(Payment.id).label("conteggio"),
        )
        .group_by("anno", "mese")
        .order_by("anno", "mese")
        .all()
    )

    monthly_data = [
        {
            "periodo": f"{int(r.mese):02d}/{int(r.anno)}",
            "totale": float(r.totale),
            "conteggio": r.conteggio,
        }
        for r in monthly
    ]

    by_bank = (
        query.with_entities(
            Payment.banca, func.sum(Payment.importo).label("totale"),
            func.count(Payment.id).label("conteggio")
        )
        .group_by(Payment.banca)
        .order_by(func.sum(Payment.importo).desc())
        .all()
    )

    bank_data = [
        {"banca": r.banca or "N/D", "totale": float(r.totale), "conteggio": r.conteggio}
        for r in by_bank
    ]

    top_clients = (
        query.with_entities(
            Payment.cliente,
            func.sum(Payment.importo).label("totale"),
            func.count(Payment.id).label("conteggio"),
        )
        .filter(Payment.cliente.isnot(None), Payment.cliente != "")
        .group_by(Payment.cliente)
        .order_by(func.sum(Payment.importo).desc())
        .limit(10)
        .all()
    )

    client_data = [
        {"cliente": r.cliente, "totale": float(r.totale), "conteggio": r.conteggio}
        for r in top_clients
    ]

    banks = [
        r[0]
        for r in db.session.query(Payment.banca).distinct().order_by(Payment.banca).all()
        if r[0]
    ]

    return jsonify({
        "kpi": {
            "totale": float(totale),
            "num_pagamenti": num_pagamenti,
            "media": round(media, 2),
            "importo_max": float(importo_max),
            "importo_min": float(importo_min),
        },
        "monthly": monthly_data,
        "by_bank": bank_data,
        "top_clients": client_data,
        "banks": banks,
    })


@main_bp.route("/api/payments")
def api_payments():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    banca = request.args.get("banca")
    importo_min = request.args.get("importo_min", type=float)
    importo_max = request.args.get("importo_max", type=float)
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "data_pagamento")
    sort_dir = request.args.get("sort_dir", "desc")

    query = Payment.query

    if date_from:
        try:
            query = query.filter(
                Payment.data_pagamento >= datetime.strptime(date_from, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                Payment.data_pagamento <= datetime.strptime(date_to, "%Y-%m-%d").date()
            )
        except ValueError:
            pass
    if banca:
        query = query.filter(Payment.banca == banca)
    if importo_min is not None:
        query = query.filter(Payment.importo >= importo_min)
    if importo_max is not None:
        query = query.filter(Payment.importo <= importo_max)
    if search:
        like_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Payment.descrizione.ilike(like_term),
                Payment.cliente.ilike(like_term),
                Payment.riferimento.ilike(like_term),
            )
        )

    sort_column = getattr(Payment, sort_by, Payment.data_pagamento)
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    banks = [
        r[0]
        for r in db.session.query(Payment.banca).distinct().order_by(Payment.banca).all()
        if r[0]
    ]

    return jsonify({
        "payments": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page,
        "per_page": per_page,
        "banks": banks,
    })


@main_bp.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "Nessun file caricato"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nessun file selezionato"}), 400

    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Il file deve essere in formato CSV"}), 400

    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            file.seek(0)
            content = file.read().decode("latin-1")
        except Exception:
            return jsonify({"error": "Impossibile leggere il file. Encoding non supportato."}), 400

    if request.form.get("action") == "preview":
        preview = preview_csv(content)
        return jsonify(preview)

    mapping_raw = request.form.get("mapping", "{}")
    try:
        import json
        column_mapping = json.loads(mapping_raw)
    except Exception:
        return jsonify({"error": "Mappatura colonne non valida"}), 400

    if not column_mapping:
        return jsonify({"error": "Nessuna mappatura colonne specificata"}), 400

    payments_data = parse_csv(content, column_mapping)

    if not payments_data:
        return jsonify({"error": "Nessun pagamento valido trovato nel file"}), 400

    upload = CsvUpload(filename=file.filename, num_records=len(payments_data))
    db.session.add(upload)
    db.session.flush()

    for pdata in payments_data:
        payment = Payment(
            data_pagamento=pdata.get("data_pagamento"),
            importo=pdata.get("importo", 0),
            banca=pdata.get("banca"),
            descrizione=pdata.get("descrizione"),
            riferimento=pdata.get("riferimento"),
            tipo_pagamento=pdata.get("tipo_pagamento"),
            cliente=pdata.get("cliente"),
            upload_id=upload.id,
        )
        db.session.add(payment)

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Caricati {len(payments_data)} pagamenti da {file.filename}",
        "upload": upload.to_dict(),
    })


@main_bp.route("/api/payments/<int:payment_id>", methods=["DELETE"])
def api_delete_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    db.session.delete(payment)
    db.session.commit()
    return jsonify({"success": True, "message": "Pagamento eliminato"})


@main_bp.route("/api/uploads/<int:upload_id>", methods=["DELETE"])
def api_delete_upload(upload_id):
    upload = CsvUpload.query.get_or_404(upload_id)
    num = upload.payments.count()
    db.session.delete(upload)
    db.session.commit()
    return jsonify({"success": True, "message": f"Upload e {num} pagamenti eliminati"})


@main_bp.route("/api/uploads")
def api_uploads():
    uploads = CsvUpload.query.order_by(CsvUpload.uploaded_at.desc()).all()
    return jsonify([u.to_dict() for u in uploads])
