import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import crud
from .bot import build_application
from .config import TELEGRAM_BOT_TOKEN
from .db import get_session, init_db
from .reminders import loop_lembretes
from .routers import dashboard, web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tvdash")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with get_session() as session:
        crud.seed_users(session)

    bot_app = None
    tarefa_lembretes = None
    if TELEGRAM_BOT_TOKEN:
        bot_app = build_application()
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Bot do Telegram rodando (polling).")
        tarefa_lembretes = asyncio.create_task(loop_lembretes(bot_app.bot))
    else:
        logger.warning("TELEGRAM_BOT_TOKEN não configurado — bot do Telegram desativado.")

    yield

    if tarefa_lembretes is not None:
        tarefa_lembretes.cancel()
    if bot_app is not None:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


app = FastAPI(title="TV Dash", lifespan=lifespan)
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).resolve().parent / "static")), name="static"
)
app.include_router(dashboard.router)
app.include_router(web.router)
