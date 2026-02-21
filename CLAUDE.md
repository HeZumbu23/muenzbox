# Freigabe-Terminal – Kinder Medienzeit

## Projektbeschreibung
WebApp zur Verwaltung von Medienzeit-Kontingenten für Kinder.
Kinder lösen "Münzen" (je 30 Min) am Terminal ein für Switch oder TV.

## Stack
- Backend: Python FastAPI + SQLite (aiosqlite)
- Frontend: React + Vite + TailwindCSS (single page, kein router nötig)
- Deployment: Docker Compose auf Proxmox
- iPad als Terminal im Guided Access / Kiosk-Modus (Browser fullscreen)

## Architektur
- Backend läuft auf Port 8420
- Frontend läuft auf Port 8421 (nginx, proxied zu Backend /api)
- Kein separater Auth-Service – PIN-Hash (bcrypt) in SQLite

## Datenmodell
### children
id, name, pin_hash, 
switch_coins (aktuell), switch_coins_weekly (wöchentlich gutgeschrieben),
switch_coins_max (Anspar-Cap),
tv_coins, tv_coins_weekly, tv_coins_max,
allowed_from (z.B. "08:00"), allowed_until (z.B. "20:00")

### sessions
id, child_id, type (switch/tv),
started_at, ends_at, coins_used, status (active/completed/cancelled)

### coin_log
id, child_id, type, delta, reason (weekly_refill/session/admin_adjust), created_at

## Münz-Logik
- 1 Münze = 30 Minuten
- Samstags 00:00: coins = min(coins + weekly, max) per Cron
- Session: coins >= 1, Zeitfenster ok, keine aktive Session
- Coins werden beim Start abgezogen (nicht am Ende)

## MikroTik Integration (Adapter Pattern)
Datei: backend/adapters/mikrotik_direct.py
Interface:
  async def tv_freigeben() -> bool
  async def tv_sperren() -> bool  
  async def tv_status() -> bool
Implementierung: RouterOS v7 REST API
  TV-IP in Address-List "tv-blocked" (disabled=true = freigegeben)
  PATCH /rest/ip/firewall/address-list/{id} {"disabled": "true/false"}
Später austauschbar gegen: backend/adapters/mikrotik_api.py

## Nintendo Switch Integration
Library: pynintendoparental
  Session start: Tageslimit auf 30min setzen
  Session end: Tageslimit auf 0 setzen (sperren)

## UI – Kinder (iPad Kiosk)
Screen 1: Kind auswählen (große Avatare/Namen)
Screen 2: PIN-Eingabe (Nummernpad, große Buttons)
Screen 3: Übersicht (Münzen Switch + TV als Münz-Icons)
Screen 4: Session läuft – Countdown + "Früher beenden"
Sprache: Deutsch, kindgerecht, große Buttons, wenig Text

## UI – Eltern (Browser)
Route: /eltern (PIN-geschützt, eigener Admin-PIN)
- Kinder verwalten (Münzen anpassen, PIN ändern, Zeitfenster)
- Aktive Sessions sehen / beenden
- Coin-History pro Kind
- Manuelle Münzen gutschreiben/abziehen

## Umgebungsvariablen (.env)
MIKROTIK_HOST=192.168.x.x
MIKROTIK_USER=freigabe-api
MIKROTIK_PASS=xxx
MIKROTIK_TV_ADDRESS_LIST_COMMENT=Fernseher
TV_IP=192.168.x.x
NINTENDO_TOKEN=xxx
ADMIN_PIN_HASH=xxx  # bcrypt
SECRET_KEY=xxx      # für session tokens

## Docker Compose
services: backend, frontend
volumes: ./data:/data  (SQLite)
network: bridge, nur intern erreichbar + reverse proxy
