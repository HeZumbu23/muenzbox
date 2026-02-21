#!/bin/bash
set -e

echo "=== Münzbox Devcontainer Setup ==="

echo "→ Backend: Python-Pakete installieren..."
pip install --quiet -r backend/requirements.txt

echo "→ Frontend: npm install..."
npm --prefix frontend install

echo "→ Daten-Verzeichnis anlegen..."
mkdir -p data

echo "→ .env aus .env.example kopieren (falls nicht vorhanden)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env angelegt – bitte ADMIN_PIN_HASH und SECRET_KEY setzen!"
else
  echo "  .env bereits vorhanden, wird nicht überschrieben."
fi

echo ""
echo "✅ Setup abgeschlossen!"
echo ""
echo "Starten mit F5 (Compound: Backend + Frontend)"
echo "oder manuell:"
echo "  Terminal 1: cd backend && uvicorn main:app --reload --port 8420"
echo "  Terminal 2: cd frontend && npm run dev"
