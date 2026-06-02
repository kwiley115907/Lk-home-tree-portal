import os


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]

    database_url = os.environ["DATABASE_URL"]

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
