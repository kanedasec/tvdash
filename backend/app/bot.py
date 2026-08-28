import logging
import re
from datetime import date, datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from . import crud
from .config import ALLOWED_CHAT_ID, TELEGRAM_BOT_TOKEN, TIMEZONE
from .db import get_session

logger = logging.getLogger("tvdash.bot")

_RECORRENCIA_RE = re.compile(r"^(?:cada\s+)?(\d+)?\s*(dias?|semanas?|m[eê]s(?:es)?)$")
_RECORRENCIA_ALIASES = {
    "diaria": ("dias", 1),
    "diário": ("dias", 1),
    "diario": ("dias", 1),
    "semanal": ("semanas", 1),
    "mensal": ("meses", 1),
}

AJUDA_RECORRENCIA = (
    "Recorrência aceita: diaria, semanal, mensal, ou \"cada N dias/semanas/meses\" (ex: cada 3 dias)."
)


def parse_recorrencia(spec: str) -> tuple[str, int] | None:
    s = spec.strip().lower()
    if s in _RECORRENCIA_ALIASES:
        return _RECORRENCIA_ALIASES[s]
    m = _RECORRENCIA_RE.match(s)
    if not m:
        return None
    n = int(m.group(1)) if m.group(1) else 1
    if n < 1:
        return None
    unidade = m.group(2)
    if unidade.startswith("dia"):
        tipo = "dias"
    elif unidade.startswith("semana"):
        tipo = "semanas"
    else:
        tipo = "meses"
    return (tipo, n)


AJUDA = (
    "Comandos disponíveis:\n\n"
    "/eusou Nome — vincula você (uma vez só) ao seu nome cadastrado\n"
    "/novatarefa Nome | peso | duracao em minutos — cadastra um tipo de tarefa\n"
    "  ex: /novatarefa Lavar louça | 3 | 15\n"
    "/editartarefa Nome | novo peso | nova duracao em minutos — edita uma tarefa já cadastrada\n"
    "  ex: /editartarefa Lavar louça | 5 | 20\n"
    "/tarefas — lista as tarefas cadastradas\n"
    "/feito Nome da tarefa | duracao_min (opcional) | DD/MM (opcional) — registra a conclusão. "
    "Sem duração usa o padrão da tarefa; sem data marca agora\n"
    "  ex: /feito Levar lixo\n"
    "  ex: /feito Levar lixo | 25\n"
    "  ex: /feito Levar lixo | 12/08\n"
    "/planejar Nome da tarefa | DD/MM | recorrencia (opcional) — agenda a tarefa pra um dia "
    "(aparece pendente até alguém marcar /feito)\n"
    "  ex: /planejar Levar lixo | 12/08\n"
    "  ex: /planejar Levar lixo | 12/08 | semanal\n"
    "/cancelartarefa Nome da tarefa | DD/MM (opcional) — cancela planejamento(s); sem data, cancela tudo\n"
    "  ex: /cancelartarefa Levar lixo\n"
    "/compromisso DD/MM HH:MM Descrição | recorrencia (opcional) — cadastra um compromisso na agenda\n"
    "  ex: /compromisso 25/12 19:00 Ceia de Natal\n"
    "  ex: /compromisso 10/08 08:00 Regar plantas | diaria\n"
    "/cancelarcompromisso Descrição | DD/MM (opcional) — cancela compromisso(s); sem data, cancela tudo\n"
    "  ex: /cancelarcompromisso Reuniao semanal\n"
    "/agenda — lista os próximos compromissos\n"
    "\n--- Atividade física ---\n"
    "/novoexercicio Nome | duracao_min padrão — cadastra um tipo de exercício\n"
    "  ex: /novoexercicio Corrida | 30\n"
    "/exercicios — lista os exercícios cadastrados\n"
    "/exercicio Nome | duracao_min (opcional) | DD/MM (opcional) — registra um checkin. "
    "Sem duração usa o padrão do exercício\n"
    "  ex: /exercicio Corrida\n"
    "  ex: /exercicio Corrida | 45\n"
    "\n" + AJUDA_RECORRENCIA + "\n"
    "\nAviso automático: todo dia, os compromissos do dia seguinte são anunciados aqui no grupo.\n"
)

_COMPROMISSO_RE = re.compile(
    r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\s+(\d{1,2}):(\d{2})\s+(.+)$", re.DOTALL
)
_PLANEJAR_DATA_RE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$")


def _texto_apos_comando(update: Update) -> str:
    texto = update.message.text or ""
    partes = texto.split(maxsplit=1)
    return partes[1].strip() if len(partes) > 1 else ""


async def _usuario_remetente(update: Update):
    with get_session() as session:
        usuario = crud.get_user_by_telegram_id(session, update.effective_user.id)
        return (usuario.id, usuario.nome) if usuario else None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Olá! Eu organizo as tarefas e a agenda de casa.\n\n" + AJUDA)


async def cmd_eusou(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    nome = _texto_apos_comando(update)
    if not nome:
        await update.message.reply_text("Uso: /eusou Nome (o nome que já está cadastrado no sistema)")
        return
    try:
        with get_session() as session:
            usuario = crud.link_user(session, nome, update.effective_user.id)
        await update.message.reply_text(f"Pronto, {usuario.nome}! Suas ações agora serão registradas com esse nome.")
    except crud.NaoEncontradoError as exc:
        await update.message.reply_text(str(exc))


async def cmd_novatarefa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) != 3 or not all(partes):
        await update.message.reply_text(
            "Uso: /novatarefa Nome | peso | duracao_min\nex: /novatarefa Lavar louça | 3 | 15"
        )
        return
    nome, peso_str, duracao_str = partes
    if not peso_str.isdigit() or not duracao_str.isdigit():
        await update.message.reply_text("Peso e duração devem ser números inteiros (minutos).")
        return
    try:
        with get_session() as session:
            tt = crud.create_task_type(session, nome, int(peso_str), int(duracao_str))
        await update.message.reply_text(
            f'Tarefa "{tt.nome}" cadastrada (peso {tt.peso}, {tt.duracao_min} min).'
        )
    except crud.NomeJaExisteError as exc:
        await update.message.reply_text(str(exc))


async def cmd_editartarefa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) != 3 or not all(partes):
        await update.message.reply_text(
            "Uso: /editartarefa Nome da tarefa | novo peso | nova duracao em minutos\n"
            "ex: /editartarefa Lavar louça | 5 | 20"
        )
        return
    nome_tarefa, peso_str, duracao_str = partes
    if not peso_str.isdigit() or not duracao_str.isdigit():
        await update.message.reply_text("Peso e duração devem ser números inteiros (minutos).")
        return

    with get_session() as session:
        tt = crud.find_task_type_by_name(session, nome_tarefa)
        if tt is None:
            await update.message.reply_text(
                f'Não encontrei (ou encontrei mais de uma) tarefa parecida com "{nome_tarefa}". '
                "Confira com /tarefas."
            )
            return
        crud.update_task_type(session, tt.id, int(peso_str), int(duracao_str))

    await update.message.reply_text(f'Tarefa "{tt.nome}" atualizada: peso {peso_str}, {duracao_str} min.')


async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        tipos = crud.list_task_types(session)
    if not tipos:
        await update.message.reply_text("Nenhuma tarefa cadastrada ainda. Use /novatarefa para criar uma.")
        return
    linhas = [f"• {t.nome} — peso {t.peso}, {t.duracao_min} min" for t in tipos]
    await update.message.reply_text("\n".join(linhas))


async def cmd_feito(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    if not texto:
        await update.message.reply_text(
            "Uso: /feito Nome da tarefa | duracao_min (opcional) | DD/MM (opcional)\n"
            "Sem duração, usa o padrão cadastrado na tarefa.\n"
            "ex: /feito Levar lixo\n"
            "ex: /feito Levar lixo | 25\n"
            "ex: /feito Levar lixo | 12/08"
        )
        return

    partes = [p.strip() for p in texto.split("|")]
    nome_tarefa = partes[0]
    duracao_min, dia_alvo, erro = _parse_duracao_e_data(partes[1:])
    if erro:
        await update.message.reply_text(erro)
        return

    remetente = await _usuario_remetente(update)
    if remetente is None:
        await update.message.reply_text(
            "Eu não sei quem você é ainda. Rode /eusou Nome (com o nome já cadastrado no sistema) primeiro."
        )
        return
    user_id, user_nome = remetente

    with get_session() as session:
        tt = crud.find_task_type_by_name(session, nome_tarefa)
        if tt is None:
            await update.message.reply_text(
                f'Não encontrei (ou encontrei mais de uma) tarefa parecida com "{nome_tarefa}". '
                "Confira com /tarefas."
            )
            return
        crud.log_task_done(session, tt.id, user_id, dia_alvo, duracao_min)

    quando = f" em {dia_alvo.strftime('%d/%m')}" if dia_alvo else " agora"
    duracao_txt = f" ({duracao_min} min)" if duracao_min is not None else ""
    await update.message.reply_text(f'Valeu, {user_nome}! Marquei "{tt.nome}" como feita{quando}{duracao_txt}.')


def _parse_data_dd_mm(data_str: str) -> date | None:
    m = _PLANEJAR_DATA_RE.match(data_str)
    if not m:
        return None
    dia, mes, ano = m.groups()
    ano = int(ano) if ano else datetime.now(TIMEZONE).year
    try:
        return date(ano, int(mes), int(dia))
    except ValueError:
        return None


def _parse_duracao_e_data(partes: list[str]) -> tuple[int | None, date | None, str | None]:
    """Classifica parâmetros extras (depois do nome) em duração (número) e/ou data (DD/MM),
    em qualquer ordem. Retorna (duracao_min, dia, mensagem_de_erro)."""
    duracao_min = None
    dia = None
    for p in partes:
        if not p:
            continue
        if p.isdigit():
            duracao_min = int(p)
            continue
        d = _parse_data_dd_mm(p)
        if d is None:
            return None, None, f'Não entendi "{p}" — use um número (minutos) ou uma data DD/MM.'
        dia = d
    return duracao_min, dia, None


async def cmd_novoexercicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) != 2 or not all(partes):
        await update.message.reply_text(
            "Uso: /novoexercicio Nome | duracao_min padrão\nex: /novoexercicio Corrida | 30"
        )
        return
    nome, duracao_str = partes
    if not duracao_str.isdigit():
        await update.message.reply_text("Duração deve ser um número inteiro (minutos).")
        return
    try:
        with get_session() as session:
            et = crud.create_exercise_type(session, nome, int(duracao_str))
        await update.message.reply_text(f'Exercício "{et.nome}" cadastrado (padrão {et.duracao_min} min).')
    except crud.NomeJaExisteError as exc:
        await update.message.reply_text(str(exc))


async def cmd_exercicios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        tipos = crud.list_exercise_types(session)
    if not tipos:
        await update.message.reply_text("Nenhum exercício cadastrado ainda. Use /novoexercicio para criar um.")
        return
    linhas = [f"• {t.nome} — padrão {t.duracao_min} min" for t in tipos]
    await update.message.reply_text("\n".join(linhas))


async def cmd_exercicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    if not texto:
        await update.message.reply_text(
            "Uso: /exercicio Nome do exercicio | duracao_min (opcional) | DD/MM (opcional)\n"
            "Sem duração, usa o padrão cadastrado no exercício.\n"
            "ex: /exercicio Corrida\n"
            "ex: /exercicio Corrida | 45\n"
            "ex: /exercicio Corrida | 10/08"
        )
        return

    partes = [p.strip() for p in texto.split("|")]
    nome_exercicio = partes[0]
    duracao_min, dia_alvo, erro = _parse_duracao_e_data(partes[1:])
    if erro:
        await update.message.reply_text(erro)
        return

    remetente = await _usuario_remetente(update)
    if remetente is None:
        await update.message.reply_text(
            "Eu não sei quem você é ainda. Rode /eusou Nome (com o nome já cadastrado no sistema) primeiro."
        )
        return
    user_id, user_nome = remetente

    with get_session() as session:
        et = crud.find_exercise_type_by_name(session, nome_exercicio)
        if et is None:
            await update.message.reply_text(
                f'Não encontrei (ou encontrei mais de um) exercício parecido com "{nome_exercicio}". '
                "Confira com /exercicios."
            )
            return
        log = crud.log_exercise(session, et.id, user_id, duracao_min, dia_alvo)
        duracao_resolvida = log.duracao_min

    quando = f" em {dia_alvo.strftime('%d/%m')}" if dia_alvo else " agora"
    await update.message.reply_text(
        f'Valeu, {user_nome}! Registrei "{et.nome}" ({duracao_resolvida} min) {quando.strip()}.'
    )


async def cmd_planejar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) not in (2, 3) or not all(partes):
        await update.message.reply_text(
            "Uso: /planejar Nome da tarefa | DD/MM | recorrencia (opcional)\n"
            "ex: /planejar Levar lixo | 12/08\n"
            "ex: /planejar Levar lixo | 12/08 | semanal\n"
            f"{AJUDA_RECORRENCIA}"
        )
        return
    nome_tarefa, data_str = partes[0], partes[1]
    data_alvo = _parse_data_dd_mm(data_str)
    if data_alvo is None:
        await update.message.reply_text("Data inválida. Use o formato DD/MM (ou DD/MM/AAAA).")
        return

    recorrencia_tipo, recorrencia_intervalo = None, None
    if len(partes) == 3:
        rec = parse_recorrencia(partes[2])
        if rec is None:
            await update.message.reply_text(f"Recorrência inválida. {AJUDA_RECORRENCIA}")
            return
        recorrencia_tipo, recorrencia_intervalo = rec

    with get_session() as session:
        tt = crud.find_task_type_by_name(session, nome_tarefa)
        if tt is None:
            await update.message.reply_text(
                f'Não encontrei (ou encontrei mais de uma) tarefa parecida com "{nome_tarefa}". '
                "Confira com /tarefas."
            )
            return
        crud.create_task_assignment(session, tt.id, data_alvo, recorrencia_tipo, recorrencia_intervalo)

    sufixo_recorrencia = f" (recorrente: {recorrencia_intervalo} {recorrencia_tipo})" if recorrencia_tipo else ""
    await update.message.reply_text(
        f'Tarefa "{tt.nome}" planejada para {data_alvo.strftime("%d/%m/%Y")}{sufixo_recorrencia}.'
    )


async def cmd_compromisso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = texto.split("|")
    principal = partes[0].strip()
    recorrencia_str = partes[1].strip() if len(partes) > 1 else None

    m = _COMPROMISSO_RE.match(principal)
    if not m:
        await update.message.reply_text(
            "Uso: /compromisso DD/MM HH:MM Descrição | recorrencia (opcional)\n"
            "ex: /compromisso 25/12 19:00 Ceia de Natal\n"
            "ex: /compromisso 10/08 08:00 Regar plantas | diaria\n"
            f"{AJUDA_RECORRENCIA}"
        )
        return
    dia, mes, ano, hora, minuto, descricao = m.groups()
    ano = int(ano) if ano else datetime.now(TIMEZONE).year
    try:
        data_local = datetime(ano, int(mes), int(dia), int(hora), int(minuto), tzinfo=TIMEZONE)
    except ValueError as exc:
        await update.message.reply_text(f"Data/hora inválida: {exc}")
        return

    recorrencia_tipo, recorrencia_intervalo = None, None
    if recorrencia_str:
        rec = parse_recorrencia(recorrencia_str)
        if rec is None:
            await update.message.reply_text(f"Recorrência inválida. {AJUDA_RECORRENCIA}")
            return
        recorrencia_tipo, recorrencia_intervalo = rec

    remetente = await _usuario_remetente(update)
    criado_por = remetente[0] if remetente else None

    with get_session() as session:
        crud.create_appointment(
            session,
            descricao.strip(),
            data_local.astimezone(timezone.utc),
            criado_por=criado_por,
            recorrencia_tipo=recorrencia_tipo,
            recorrencia_intervalo=recorrencia_intervalo,
        )

    sufixo_recorrencia = f" (recorrente: {recorrencia_intervalo} {recorrencia_tipo})" if recorrencia_tipo else ""
    await update.message.reply_text(
        f'Compromisso "{descricao.strip()}" marcado para {data_local.strftime("%d/%m/%Y %H:%M")}{sufixo_recorrencia}.'
    )


async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        compromissos = crud.list_upcoming_appointments(session)
    if not compromissos:
        await update.message.reply_text("Nenhum compromisso futuro cadastrado.")
        return
    linhas = []
    for c in compromissos:
        data_str = c["data_hora_utc"].astimezone(TIMEZONE).strftime("%d/%m %H:%M")
        sufixo = " (recorrente)" if c["recorrente"] else ""
        linhas.append(f"• {data_str}{sufixo} — {c['titulo']}")
    await update.message.reply_text("\n".join(linhas))


async def cmd_cancelartarefa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) not in (1, 2) or not partes[0]:
        await update.message.reply_text(
            "Uso: /cancelartarefa Nome da tarefa | DD/MM (opcional)\n"
            "Sem data, cancela TODOS os planejamentos dessa tarefa (inclusive recorrências).\n"
            "ex: /cancelartarefa Levar lixo\n"
            "ex: /cancelartarefa Levar lixo | 12/08"
        )
        return

    nome_tarefa = partes[0]
    data_alvo = None
    if len(partes) == 2 and partes[1]:
        data_alvo = _parse_data_dd_mm(partes[1])
        if data_alvo is None:
            await update.message.reply_text("Data inválida. Use o formato DD/MM (ou DD/MM/AAAA).")
            return

    with get_session() as session:
        tt = crud.find_task_type_by_name(session, nome_tarefa)
        if tt is None:
            await update.message.reply_text(
                f'Não encontrei (ou encontrei mais de uma) tarefa parecida com "{nome_tarefa}". '
                "Confira com /tarefas."
            )
            return
        n = crud.cancel_task_assignments(session, tt.id, data_alvo)

    if n == 0:
        await update.message.reply_text(f'Não havia planejamento de "{tt.nome}" pra cancelar.')
    else:
        sufixo = f" em {data_alvo.strftime('%d/%m')}" if data_alvo else " (todos, inclusive recorrências)"
        await update.message.reply_text(f'Cancelado{sufixo}: "{tt.nome}".')


async def cmd_cancelarcompromisso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    texto = _texto_apos_comando(update)
    partes = [p.strip() for p in texto.split("|")]
    if len(partes) not in (1, 2) or not partes[0]:
        await update.message.reply_text(
            "Uso: /cancelarcompromisso Descrição | DD/MM (opcional)\n"
            "Sem data, cancela TODOS os compromissos com esse título (inclusive recorrências).\n"
            "ex: /cancelarcompromisso Reuniao semanal"
        )
        return

    titulo_busca = partes[0]
    data_alvo = None
    if len(partes) == 2 and partes[1]:
        data_alvo = _parse_data_dd_mm(partes[1])
        if data_alvo is None:
            await update.message.reply_text("Data inválida. Use o formato DD/MM (ou DD/MM/AAAA).")
            return

    with get_session() as session:
        n = crud.cancel_appointments(session, titulo_busca, data_alvo)

    if n == 0:
        await update.message.reply_text(f'Não encontrei nenhum compromisso com "{titulo_busca}" pra cancelar.')
    else:
        await update.message.reply_text(f'Cancelado(s) {n} compromisso(s) com "{titulo_busca}".')


def build_application() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurado no .env")
    if not ALLOWED_CHAT_ID:
        logger.warning(
            "ALLOWED_CHAT_ID não configurado — o bot não vai responder a nenhum comando. "
            "Rode get_chat_id.py para descobrir o chat_id do grupo."
        )

    grupo_autorizado = filters.Chat(chat_id=ALLOWED_CHAT_ID) if ALLOWED_CHAT_ID else filters.Chat(chat_id=-1)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start, filters=grupo_autorizado))
    app.add_handler(CommandHandler("ajuda", cmd_start, filters=grupo_autorizado))
    app.add_handler(CommandHandler("eusou", cmd_eusou, filters=grupo_autorizado))
    app.add_handler(CommandHandler("novatarefa", cmd_novatarefa, filters=grupo_autorizado))
    app.add_handler(CommandHandler("editartarefa", cmd_editartarefa, filters=grupo_autorizado))
    app.add_handler(CommandHandler("tarefas", cmd_tarefas, filters=grupo_autorizado))
    app.add_handler(CommandHandler("feito", cmd_feito, filters=grupo_autorizado))
    app.add_handler(CommandHandler("novoexercicio", cmd_novoexercicio, filters=grupo_autorizado))
    app.add_handler(CommandHandler("exercicios", cmd_exercicios, filters=grupo_autorizado))
    app.add_handler(CommandHandler("exercicio", cmd_exercicio, filters=grupo_autorizado))
    app.add_handler(CommandHandler("planejar", cmd_planejar, filters=grupo_autorizado))
    app.add_handler(CommandHandler("cancelartarefa", cmd_cancelartarefa, filters=grupo_autorizado))
    app.add_handler(CommandHandler("compromisso", cmd_compromisso, filters=grupo_autorizado))
    app.add_handler(CommandHandler("cancelarcompromisso", cmd_cancelarcompromisso, filters=grupo_autorizado))
    app.add_handler(CommandHandler("agenda", cmd_agenda, filters=grupo_autorizado))
    return app
