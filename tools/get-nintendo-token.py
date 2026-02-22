"""
Nintendo Account Session-Token holen.

Voraussetzung:
    pip install pynintendoparental

Ausführen:
    python get-nintendo-token.py
"""
import asyncio
from pynintendoparental import Authenticator


async def main():
    auth = Authenticator()
    print()
    print("=== Nintendo Token holen ===")
    print()
    print("1. Oeffne diese URL im Browser:")
    print()
    print(auth.login_url)
    print()
    print("2. Mit dem Nintendo-Account einloggen (der Eltern-Account der Kindersicherung)")
    print("3. Den Button 'Diese Person auswaehlen' SEHEN – aber NICHT klicken!")
    print("4. Stattdessen: Rechtsklick auf den Button → 'Link-Adresse kopieren'")
    print("   (Die URL beginnt mit npf...://...)")
    print()
    url = input("Kopierte URL hier einfuegen und Enter druecken: ").strip()

    await auth.complete_login(url)

    print()
    print("=== Erfolg! ===")
    print()
    print("Trage diesen Wert in deine .env ein:")
    print()
    print(f"NINTENDO_TOKEN={auth.session_token}")
    print()


asyncio.run(main())
