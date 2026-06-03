#!/usr/bin/env bash

pip install -r requirements.txt

python - <<'PYTHON'
from app import app
from models import db

app.app_context().push()
db.create_all()

print("Database tables created.")
PYTHON

python create_admin.py
