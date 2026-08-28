"""
Utilitário único: descobre o chat_id de um grupo do Telegram.

Como usar:
1. Adicione o bot ao grupo privado (só você e sua esposa).
2. Mande qualquer mensagem no grupo (ex: "oi").
3. Rode este script: python get_chat_id.py
4. Copie o chat_id impresso para ALLOWED_CHAT_ID no arquivo .env.
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    sys.exit("Configure TELEGRAM_BOT_TOKEN no .env antes de rodar este script.")

resp = httpx.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10)
resp.raise_for_status()
updates = resp.json().get("result", [])

if not updates:
    sys.exit(
        "Nenhuma mensagem recebida ainda. Mande uma mensagem no grupo com o bot já adicionado e rode de novo."
    )

vistos = {}
for u in updates:
    msg = u.get("message") or u.get("channel_post")
    if not msg:
        continue
    chat = msg["chat"]
    vistos[chat["id"]] = chat

for chat_id, chat in vistos.items():
    print(f"chat_id={chat_id}  tipo={chat.get('type')}  titulo/nome={chat.get('title') or chat.get('first_name')}")
