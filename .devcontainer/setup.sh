#!/bin/bash
set -e

echo "=== Münzbox Devcontainer Setup ==="

echo "→ Python Nintendo-Bridge: pynintendoparental + aiohttp installieren..."
pip install --quiet pynintendoparental aiohttp

echo "→ ASP.NET-Backend: dotnet restore + build..."
dotnet restore backend-dotnet/MuenzboxApi/MuenzboxApi.csproj
dotnet build   backend-dotnet/MuenzboxApi/MuenzboxApi.csproj -c Debug --no-restore

echo "→ Frontend: npm install..."
npm --prefix frontend install

echo "→ Daten-Verzeichnis anlegen..."
mkdir -p data

echo "→ .env aus .env.example kopieren (falls nicht vorhanden)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env angelegt – bitte ADMIN_PIN und SECRET_KEY setzen!"
else
  echo "  .env bereits vorhanden, wird nicht überschrieben."
fi

echo ""
echo "✅ Setup abgeschlossen!"
echo ""
echo "Starten mit F5: 'Backend + Frontend'"
echo ""
echo "Manuell:"
echo "  cd backend-dotnet && dotnet run --project MuenzboxApi"
echo "  cd frontend && npm run dev"
