import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Bot

from . import crud
from .config import ALLOWED_CHAT_ID, REMINDER_HOUR, TIMEZONE
from .db import get_session

logger = logging.getLogger("tvdash.reminders")


def _proxima_execucao(agora_local: datetime) -> datetime:
    hoje_no_horario = agora_local.replace(hour=REMINDER_HOUR, minute=0, second=0, microsecond=0)
    if agora_local >= hoje_no_horario:
        return hoje_no_horario + timedelta(days=1)
    return hoje_no_horario


async def enviar_lembretes(bot: Bot) -> None:
    with get_session() as session:
        compromissos = crud.compromissos_de_amanha(session)

    if not compromissos or not ALLOWED_CHAT_ID:
        return

    linhas = ["📅 Compromissos de amanhã:"]
    linhas += [f"• {c['hora']} — {c['titulo']}" for c in compromissos]
    await bot.send_message(chat_id=ALLOWED_CHAT_ID, text="\n".join(linhas))


async def loop_lembretes(bot: Bot) -> None:
    while True:
        agora_local = datetime.now(TIMEZONE)
        proxima = _proxima_execucao(agora_local)
        espera_segundos = (proxima - agora_local).total_seconds()
        logger.info(f"Próximo check de lembretes em {espera_segundos / 3600:.1f}h ({proxima})")
        await asyncio.sleep(espera_segundos)
        try:
            await enviar_lembretes(bot)
        except Exception:
            logger.exception("Falha ao enviar lembretes de compromissos")
