import asyncio
from pynintendoparental import Authenticator

async def main():
    auth = Authenticator()
    print("\n1. Öffne diese URL im Browser:")
    print(auth.login_url)
    print("\n2. Mit Nintendo-Account einloggen")
    print("3. Auf 'Diese Person auswählen' klicken – ABER NICHT KLICKEN!")
    print("4. Stattdessen: Rechtsklick → Link-Adresse kopieren")
    url = input("\nKopierte URL hier einfügen: ").strip()
    await auth.async_complete_login(url)
    print(f"\nNINTENDO_TOKEN={auth.session_token}")

asyncio.run(main())
