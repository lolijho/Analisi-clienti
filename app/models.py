from datetime import datetime

from app import db


class CsvUpload(db.Model):
    __tablename__ = "csv_uploads"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    num_records = db.Column(db.Integer, default=0)

    payments = db.relationship(
        "Payment", backref="upload", lazy="dynamic", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "uploaded_at": self.uploaded_at.strftime("%d/%m/%Y %H:%M"),
            "num_records": self.num_records,
        }


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    data_pagamento = db.Column(db.Date, nullable=False)
    importo = db.Column(db.Numeric(12, 2), nullable=False)
    banca = db.Column(db.String(100), nullable=True)
    descrizione = db.Column(db.Text, nullable=True)
    riferimento = db.Column(db.String(200), nullable=True)
    tipo_pagamento = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    upload_id = db.Column(db.Integer, db.ForeignKey("csv_uploads.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "data_pagamento": (
                self.data_pagamento.strftime("%d/%m/%Y") if self.data_pagamento else None
            ),
            "importo": float(self.importo) if self.importo else 0,
            "banca": self.banca,
            "descrizione": self.descrizione,
            "riferimento": self.riferimento,
            "tipo_pagamento": self.tipo_pagamento,
            "cliente": self.cliente,
            "created_at": self.created_at.strftime("%d/%m/%Y %H:%M"),
            "upload_id": self.upload_id,
        }
