import os


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "chiave-segreta-di-default-cambiami")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@db:5432/pagamenti"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
