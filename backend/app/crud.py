import calendar
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, select, true
from sqlalchemy.orm import Session

from .config import TIMEZONE, USER_NAMES
from .models import Appointment, ExerciseLog, ExerciseType, TaskAssignment, TaskLog, TaskType, User

TIPOS_RECORRENCIA = ("dias", "semanas", "meses")


class NomeJaExisteError(Exception):
    pass


class NaoEncontradoError(Exception):
    pass


def as_utc(dt: datetime) -> datetime:
    """SQLite descarta o tzinfo ao ler DateTime de volta — como sempre gravamos em UTC,
    reanexamos timezone.utc antes de qualquer conversão para exibição."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# --- recorrência ---------------------------------------------------------------

def _somar_meses(d: date, n: int) -> date:
    mes_total = (d.month - 1) + n
    ano = d.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(d.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def ocorre_no_dia(base: date, tipo: str, intervalo: int, alvo: date) -> bool:
    """Se uma recorrência (tipo/intervalo) com primeira ocorrência em `base` cai em `alvo`."""
    if alvo < base:
        return False
    if tipo == "dias":
        return (alvo - base).days % intervalo == 0
    if tipo == "semanas":
        return (alvo - base).days % (intervalo * 7) == 0
    if tipo == "meses":
        k = 0
        candidato = base
        while candidato < alvo:
            k += 1
            candidato = _somar_meses(base, k * intervalo)  # sempre a partir da base original, sem "arrastar" o dia
        return candidato == alvo
    raise ValueError(f'Tipo de recorrência inválido: "{tipo}"')


def proxima_ocorrencia(base: date, tipo: str, intervalo: int, a_partir_de: date) -> date:
    """Menor data >= a_partir_de em que a recorrência (tipo/intervalo, começando em `base`) ocorre."""
    if a_partir_de <= base:
        return base
    if tipo == "dias":
        passo = intervalo
    elif tipo == "semanas":
        passo = intervalo * 7
    elif tipo == "meses":
        k = 0
        candidato = base
        while candidato < a_partir_de:
            k += 1
            candidato = _somar_meses(base, k * intervalo)
        return candidato
    else:
        raise ValueError(f'Tipo de recorrência inválido: "{tipo}"')

    diff = (a_partir_de - base).days
    resto = diff % passo
    return a_partir_de if resto == 0 else a_partir_de + timedelta(days=passo - resto)


# --- setup ---------------------------------------------------------------

def seed_users(session: Session) -> None:
    existentes = {u.nome for u in session.scalars(select(User))}
    for nome in USER_NAMES:
        if nome not in existentes:
            session.add(User(nome=nome))


# --- usuários --------------------------------------------------------------

def get_user_by_telegram_id(session: Session, telegram_user_id: int) -> User | None:
    return session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))


def link_user(session: Session, nome: str, telegram_user_id: int) -> User:
    usuario = session.scalar(select(User).where(func.lower(User.nome) == nome.lower()))
    if usuario is None:
        raise NaoEncontradoError(f'Nenhum usuário cadastrado com o nome "{nome}".')
    usuario.telegram_user_id = telegram_user_id
    session.flush()
    return usuario


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.nome)))


# --- tipos de tarefa ---------------------------------------------------------

def create_task_type(session: Session, nome: str, peso: int, duracao_min: int) -> TaskType:
    existente = session.scalar(select(TaskType).where(func.lower(TaskType.nome) == nome.lower()))
    if existente is not None:
        raise NomeJaExisteError(f'Já existe uma tarefa chamada "{existente.nome}".')
    tt = TaskType(nome=nome, peso=peso, duracao_min=duracao_min)
    session.add(tt)
    session.flush()
    return tt


def update_task_type(session: Session, task_type_id: int, peso: int, duracao_min: int) -> TaskType:
    tt = session.get(TaskType, task_type_id)
    if tt is None:
        raise NaoEncontradoError("Tarefa não encontrada.")
    tt.peso = peso
    tt.duracao_min = duracao_min
    session.flush()
    return tt


def list_task_types(session: Session, only_active: bool = True) -> list[TaskType]:
    stmt = select(TaskType).order_by(TaskType.nome)
    if only_active:
        stmt = stmt.where(TaskType.ativo.is_(True))
    return list(session.scalars(stmt))


def find_task_type_by_name(session: Session, nome: str) -> TaskType | None:
    exato = session.scalar(select(TaskType).where(func.lower(TaskType.nome) == nome.lower()))
    if exato is not None:
        return exato
    candidatos = list(
        session.scalars(select(TaskType).where(func.lower(TaskType.nome).contains(nome.lower())))
    )
    return candidatos[0] if len(candidatos) == 1 else None


# --- registro de conclusão --------------------------------------------------

def log_task_done(
    session: Session,
    task_type_id: int,
    user_id: int,
    dia: date | None = None,
    duracao_min: int | None = None,
) -> TaskLog:
    """Se `dia` for informado, registra a conclusão nesse dia (ao meio-dia local) em vez de agora —
    útil pra marcar retroativamente um planejamento de um dia que passou em branco.
    Se `duracao_min` não for informado, usa a duração padrão cadastrada na tarefa; o valor
    resolvido fica gravado neste registro (métricas somam o registro, não o cadastro)."""
    if duracao_min is None:
        tt = session.get(TaskType, task_type_id)
        duracao_min = tt.duracao_min

    if dia is not None:
        done_at = datetime.combine(dia, datetime.min.time().replace(hour=12), tzinfo=TIMEZONE).astimezone(
            timezone.utc
        )
        log = TaskLog(task_type_id=task_type_id, user_id=user_id, done_at=done_at, duracao_min=duracao_min)
    else:
        log = TaskLog(task_type_id=task_type_id, user_id=user_id, duracao_min=duracao_min)
    session.add(log)
    session.flush()
    return log


# --- tarefas planejadas -----------------------------------------------------

def create_task_assignment(
    session: Session,
    task_type_id: int,
    data_alvo: date,
    recorrencia_tipo: str | None = None,
    recorrencia_intervalo: int | None = None,
) -> TaskAssignment:
    ta = TaskAssignment(
        task_type_id=task_type_id,
        data=data_alvo,
        recorrencia_tipo=recorrencia_tipo,
        recorrencia_intervalo=recorrencia_intervalo,
    )
    session.add(ta)
    session.flush()
    return ta


def cancel_task_assignments(session: Session, task_type_id: int, data: date | None = None) -> int:
    """Remove planejamentos de uma tarefa. Sem `data`, remove todos (inclusive recorrências)."""
    stmt = select(TaskAssignment).where(TaskAssignment.task_type_id == task_type_id)
    if data is not None:
        stmt = stmt.where(TaskAssignment.data == data)
    assignments = list(session.scalars(stmt))
    for ta in assignments:
        session.delete(ta)
    return len(assignments)


# --- compromissos ------------------------------------------------------------

def create_appointment(
    session: Session,
    titulo: str,
    data_hora: datetime,
    descricao: str | None = None,
    criado_por: int | None = None,
    recorrencia_tipo: str | None = None,
    recorrencia_intervalo: int | None = None,
) -> Appointment:
    ap = Appointment(
        titulo=titulo,
        data_hora=data_hora,
        descricao=descricao,
        criado_por=criado_por,
        recorrencia_tipo=recorrencia_tipo,
        recorrencia_intervalo=recorrencia_intervalo,
    )
    session.add(ap)
    session.flush()
    return ap


def find_appointments_by_titulo(session: Session, titulo: str) -> list[Appointment]:
    return list(
        session.scalars(select(Appointment).where(func.lower(Appointment.titulo).contains(titulo.lower())))
    )


def cancel_appointments(session: Session, titulo: str, data: date | None = None) -> int:
    """Remove compromissos pelo título (substring). Sem `data`, remove todos que casarem
    (inclusive recorrências)."""
    candidatos = find_appointments_by_titulo(session, titulo)
    if data is not None:
        candidatos = [ap for ap in candidatos if as_utc(ap.data_hora).astimezone(TIMEZONE).date() == data]
    for ap in candidatos:
        session.delete(ap)
    return len(candidatos)


def list_upcoming_appointments(session: Session, limit: int = 10) -> list[dict]:
    agora_utc = datetime.now(timezone.utc)
    hoje_local = datetime.now(TIMEZONE).date()

    candidatos = []
    for ap in session.scalars(select(Appointment)):
        base_local = as_utc(ap.data_hora).astimezone(TIMEZONE)
        if ap.recorrencia_tipo:
            data_ocorrencia = proxima_ocorrencia(
                base_local.date(), ap.recorrencia_tipo, ap.recorrencia_intervalo, hoje_local
            )
            data_hora_local = datetime.combine(data_ocorrencia, base_local.time(), tzinfo=TIMEZONE)
        else:
            data_hora_local = base_local

        data_hora_utc = data_hora_local.astimezone(timezone.utc)
        if data_hora_utc >= agora_utc:
            candidatos.append(
                {
                    "id": ap.id,
                    "titulo": ap.titulo,
                    "data_hora_utc": data_hora_utc,
                    "recorrente": bool(ap.recorrencia_tipo),
                }
            )

    candidatos.sort(key=lambda c: c["data_hora_utc"])
    return candidatos[:limit]


def compromissos_de_amanha(session: Session) -> list[dict]:
    hoje_local = datetime.now(TIMEZONE).date()
    amanha_local = hoje_local + timedelta(days=1)

    resultado = []
    for ap in session.scalars(select(Appointment)):
        base_local = as_utc(ap.data_hora).astimezone(TIMEZONE)
        if ap.recorrencia_tipo:
            ocorre = ocorre_no_dia(base_local.date(), ap.recorrencia_tipo, ap.recorrencia_intervalo, amanha_local)
        else:
            ocorre = base_local.date() == amanha_local
        if ocorre:
            resultado.append({"titulo": ap.titulo, "hora": base_local.strftime("%H:%M")})

    resultado.sort(key=lambda c: c["hora"])
    return resultado


# --- períodos ----------------------------------------------------------------

def period_bounds(periodo: str) -> tuple[datetime | None, datetime | None]:
    """Retorna (inicio_utc, fim_utc) para 'semana' (seg-dom), 'mes' ou 'ano' (calendário) ou 'total'
    (sem filtro)."""
    if periodo == "total":
        return None, None

    agora_local = datetime.now(TIMEZONE)

    if periodo == "semana":
        inicio_local = (agora_local - timedelta(days=agora_local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif periodo == "mes":
        inicio_local = agora_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "ano":
        inicio_local = agora_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f'Período inválido: "{periodo}" (use semana, mes, ano ou total)')

    return inicio_local.astimezone(timezone.utc), None


def _date_condition(periodo: str, coluna):
    """Condição de data (numa coluna qualquer) pra usar dentro do ON de um outer join
    (preserva linhas sem log)."""
    inicio, fim = period_bounds(periodo)
    condicoes = []
    if inicio is not None:
        condicoes.append(coluna >= inicio)
    if fim is not None:
        condicoes.append(coluna < fim)
    return and_(*condicoes) if condicoes else true()


def _intervalo_local(periodo: str) -> tuple[date, date]:
    """(inicio, fim) em data local, inclusive, para 'semana' (seg-dom), 'mes' ou 'ano' (calendário)."""
    hoje = datetime.now(TIMEZONE).date()
    if periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = inicio + timedelta(days=6)
    elif periodo == "mes":
        inicio = hoje.replace(day=1)
        fim = hoje.replace(day=calendar.monthrange(hoje.year, hoje.month)[1])
    elif periodo == "ano":
        inicio = hoje.replace(month=1, day=1)
        fim = hoje.replace(month=12, day=31)
    else:
        raise ValueError(f'Período inválido: "{periodo}" (use semana, mes ou ano)')
    return inicio, fim


# --- dashboards ----------------------------------------------------------------

def ranking_geral(session: Session, periodo: str) -> list[dict]:
    condicao = and_(TaskLog.user_id == User.id, _date_condition(periodo, TaskLog.done_at))
    stmt = (
        select(User.id, User.nome, func.coalesce(func.sum(TaskType.peso), 0), func.count(TaskLog.id))
        .select_from(User)
        .outerjoin(TaskLog, condicao)
        .outerjoin(TaskType, TaskType.id == TaskLog.task_type_id)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(TaskType.peso), 0).desc())
    )

    return [
        {"usuario_id": uid, "nome": nome, "pontos": pontos, "qtd": qtd}
        for uid, nome, pontos, qtd in session.execute(stmt).all()
    ]


def ranking_por_atividade(session: Session, task_type_id: int, periodo: str) -> list[dict]:
    condicao = and_(
        TaskLog.user_id == User.id,
        TaskLog.task_type_id == task_type_id,
        _date_condition(periodo, TaskLog.done_at),
    )
    stmt = (
        select(User.id, User.nome, func.count(TaskLog.id))
        .select_from(User)
        .outerjoin(TaskLog, condicao)
        .group_by(User.id)
        .order_by(func.count(TaskLog.id).desc())
    )

    return [
        {"usuario_id": uid, "nome": nome, "qtd": qtd} for uid, nome, qtd in session.execute(stmt).all()
    ]


def tempo_por_atividade(session: Session, periodo: str) -> list[dict]:
    """Soma a duração gravada em cada TaskLog (o valor resolvido no checkin — override ou o
    padrão da tarefa em vigor naquele momento), não o cadastro atual da tarefa."""
    condicao = and_(TaskLog.task_type_id == TaskType.id, _date_condition(periodo, TaskLog.done_at))
    stmt = (
        select(
            TaskType.id,
            TaskType.nome,
            func.count(TaskLog.id),
            func.coalesce(func.sum(TaskLog.duracao_min), 0),
        )
        .select_from(TaskType)
        .join(TaskLog, condicao)
        .group_by(TaskType.id)
        .order_by(func.coalesce(func.sum(TaskLog.duracao_min), 0).desc())
    )

    return [
        {"task_type_id": tid, "nome": nome, "qtd": qtd, "minutos_totais": minutos}
        for tid, nome, qtd, minutos in session.execute(stmt).all()
    ]


def peso_por_atividade(session: Session, periodo: str) -> list[dict]:
    """Peso acumulado por tarefa no período (peso do tipo × nº de conclusões) — diferente da
    duração, o peso é fixo no cadastro da tarefa, não tem override por checkin."""
    condicao = and_(TaskLog.task_type_id == TaskType.id, _date_condition(periodo, TaskLog.done_at))
    stmt = (
        select(TaskType.id, TaskType.nome, TaskType.peso, func.count(TaskLog.id))
        .select_from(TaskType)
        .join(TaskLog, condicao)
        .group_by(TaskType.id)
    )

    resultados = [
        {"task_type_id": tid, "nome": nome, "qtd": qtd, "peso_total": peso * qtd}
        for tid, nome, peso, qtd in session.execute(stmt).all()
    ]
    resultados.sort(key=lambda r: r["peso_total"], reverse=True)
    return resultados


def tempo_por_pessoa(session: Session, periodo: str) -> list[dict]:
    condicao = and_(TaskLog.user_id == User.id, _date_condition(periodo, TaskLog.done_at))
    stmt = (
        select(User.id, User.nome, func.coalesce(func.sum(TaskLog.duracao_min), 0))
        .select_from(User)
        .outerjoin(TaskLog, condicao)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(TaskLog.duracao_min), 0).desc())
    )

    return [
        {"usuario_id": uid, "nome": nome, "minutos_totais": minutos}
        for uid, nome, minutos in session.execute(stmt).all()
    ]


NOMES_DIA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def calendario_tarefas(session: Session, periodo: str) -> list[dict]:
    """Calendário (semana/mes/ano): tarefas concluídas/planejadas e compromissos por dia."""
    inicio, fim = _intervalo_local(periodo)
    num_dias = (fim - inicio).days + 1
    inicio_utc = datetime.combine(inicio, datetime.min.time(), tzinfo=TIMEZONE).astimezone(timezone.utc)
    fim_utc = datetime.combine(fim + timedelta(days=1), datetime.min.time(), tzinfo=TIMEZONE).astimezone(
        timezone.utc
    )

    dias = [
        {
            "data": inicio + timedelta(days=i),
            "dia_semana": NOMES_DIA[(inicio + timedelta(days=i)).weekday()],
            "tarefas": [],
            "compromissos": [],
        }
        for i in range(num_dias)
    ]

    def _idx(d: date) -> int:
        return (d - inicio).days

    logs = session.execute(
        select(TaskLog.done_at, TaskLog.task_type_id, TaskType.nome)
        .join(TaskType, TaskType.id == TaskLog.task_type_id)
        .where(TaskLog.done_at >= inicio_utc, TaskLog.done_at < fim_utc)
    ).all()
    feitos_por_dia: dict[int, set[int]] = {i: set() for i in range(num_dias)}
    nome_por_task_type: dict[int, str] = {}
    for done_at, task_type_id, nome in logs:
        idx = _idx(as_utc(done_at).astimezone(TIMEZONE).date())
        if 0 <= idx < num_dias:
            feitos_por_dia[idx].add(task_type_id)
            nome_por_task_type[task_type_id] = nome

    planejados_por_dia: dict[int, set[int]] = {i: set() for i in range(num_dias)}

    def _registrar_planejado(idx: int, task_type_id: int, nome: str) -> None:
        feita = task_type_id in feitos_por_dia[idx]
        dias[idx]["tarefas"].append({"nome": nome, "status": "feita" if feita else "pendente"})
        planejados_por_dia[idx].add(task_type_id)

    assignments_unicos = session.execute(
        select(TaskAssignment.data, TaskAssignment.task_type_id, TaskType.nome)
        .join(TaskType, TaskType.id == TaskAssignment.task_type_id)
        .where(
            TaskAssignment.recorrencia_tipo.is_(None),
            TaskAssignment.data >= inicio,
            TaskAssignment.data <= fim,
        )
    ).all()
    for data_alvo, task_type_id, nome in assignments_unicos:
        idx = _idx(data_alvo)
        if 0 <= idx < num_dias:
            _registrar_planejado(idx, task_type_id, nome)

    assignments_recorrentes = session.execute(
        select(
            TaskAssignment.data,
            TaskAssignment.recorrencia_tipo,
            TaskAssignment.recorrencia_intervalo,
            TaskAssignment.task_type_id,
            TaskType.nome,
        )
        .join(TaskType, TaskType.id == TaskAssignment.task_type_id)
        .where(TaskAssignment.recorrencia_tipo.is_not(None))
    ).all()
    for data_base, tipo, intervalo, task_type_id, nome in assignments_recorrentes:
        for idx in range(num_dias):
            dia_alvo = inicio + timedelta(days=idx)
            if ocorre_no_dia(data_base, tipo, intervalo, dia_alvo):
                _registrar_planejado(idx, task_type_id, nome)

    for idx, ids_feitos in feitos_por_dia.items():
        for task_type_id in ids_feitos:
            if task_type_id not in planejados_por_dia[idx]:
                dias[idx]["tarefas"].append({"nome": nome_por_task_type[task_type_id], "status": "feita"})

    compromissos_unicos = session.execute(
        select(Appointment.data_hora, Appointment.titulo).where(
            Appointment.recorrencia_tipo.is_(None),
            Appointment.data_hora >= inicio_utc,
            Appointment.data_hora < fim_utc,
        )
    ).all()
    for data_hora, titulo in compromissos_unicos:
        local_dt = as_utc(data_hora).astimezone(TIMEZONE)
        idx = _idx(local_dt.date())
        if 0 <= idx < num_dias:
            dias[idx]["compromissos"].append({"titulo": titulo, "hora": local_dt.strftime("%H:%M")})

    compromissos_recorrentes = session.execute(
        select(
            Appointment.data_hora,
            Appointment.recorrencia_tipo,
            Appointment.recorrencia_intervalo,
            Appointment.titulo,
        ).where(Appointment.recorrencia_tipo.is_not(None))
    ).all()
    for data_hora, tipo, intervalo, titulo in compromissos_recorrentes:
        base_local = as_utc(data_hora).astimezone(TIMEZONE)
        for idx in range(num_dias):
            dia_alvo = inicio + timedelta(days=idx)
            if ocorre_no_dia(base_local.date(), tipo, intervalo, dia_alvo):
                dias[idx]["compromissos"].append({"titulo": titulo, "hora": base_local.strftime("%H:%M")})

    for dia in dias:
        dia["compromissos"].sort(key=lambda c: c["hora"])

    return dias


# --- exercícios ----------------------------------------------------------------

def create_exercise_type(session: Session, nome: str, duracao_min: int) -> ExerciseType:
    existente = session.scalar(select(ExerciseType).where(func.lower(ExerciseType.nome) == nome.lower()))
    if existente is not None:
        raise NomeJaExisteError(f'Já existe um exercício chamado "{existente.nome}".')
    et = ExerciseType(nome=nome, duracao_min=duracao_min)
    session.add(et)
    session.flush()
    return et


def list_exercise_types(session: Session, only_active: bool = True) -> list[ExerciseType]:
    stmt = select(ExerciseType).order_by(ExerciseType.nome)
    if only_active:
        stmt = stmt.where(ExerciseType.ativo.is_(True))
    return list(session.scalars(stmt))


def find_exercise_type_by_name(session: Session, nome: str) -> ExerciseType | None:
    exato = session.scalar(select(ExerciseType).where(func.lower(ExerciseType.nome) == nome.lower()))
    if exato is not None:
        return exato
    candidatos = list(
        session.scalars(select(ExerciseType).where(func.lower(ExerciseType.nome).contains(nome.lower())))
    )
    return candidatos[0] if len(candidatos) == 1 else None


def log_exercise(
    session: Session,
    exercise_type_id: int,
    user_id: int,
    duracao_min: int | None = None,
    dia: date | None = None,
) -> ExerciseLog:
    """Se `duracao_min` não for informado, usa a duração padrão cadastrada no tipo de exercício;
    o valor resolvido fica gravado neste registro (métricas somam o registro, não o cadastro)."""
    if duracao_min is None:
        et = session.get(ExerciseType, exercise_type_id)
        duracao_min = et.duracao_min

    if dia is not None:
        feito_em = datetime.combine(dia, datetime.min.time().replace(hour=12), tzinfo=TIMEZONE).astimezone(
            timezone.utc
        )
        log = ExerciseLog(
            exercise_type_id=exercise_type_id, user_id=user_id, duracao_min=duracao_min, feito_em=feito_em
        )
    else:
        log = ExerciseLog(exercise_type_id=exercise_type_id, user_id=user_id, duracao_min=duracao_min)
    session.add(log)
    session.flush()
    return log


def ranking_exercicio_pessoa(session: Session, periodo: str) -> list[dict]:
    """Por pessoa: tempo total e número de checkins. Ordenado por tempo desc — pra ranking por
    checkins, o chamador só precisa reordenar essa mesma lista."""
    condicao = and_(ExerciseLog.user_id == User.id, _date_condition(periodo, ExerciseLog.feito_em))
    stmt = (
        select(
            User.id,
            User.nome,
            func.coalesce(func.sum(ExerciseLog.duracao_min), 0),
            func.count(ExerciseLog.id),
        )
        .select_from(User)
        .outerjoin(ExerciseLog, condicao)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(ExerciseLog.duracao_min), 0).desc())
    )

    return [
        {"usuario_id": uid, "nome": nome, "minutos_totais": minutos, "checkins": checkins}
        for uid, nome, minutos, checkins in session.execute(stmt).all()
    ]


def tempo_por_tipo_exercicio(session: Session, periodo: str) -> list[dict]:
    condicao = and_(ExerciseLog.exercise_type_id == ExerciseType.id, _date_condition(periodo, ExerciseLog.feito_em))
    stmt = (
        select(
            ExerciseType.id,
            ExerciseType.nome,
            func.count(ExerciseLog.id),
            func.coalesce(func.sum(ExerciseLog.duracao_min), 0),
        )
        .select_from(ExerciseType)
        .join(ExerciseLog, condicao)
        .group_by(ExerciseType.id)
        .order_by(func.coalesce(func.sum(ExerciseLog.duracao_min), 0).desc())
    )

    return [
        {"exercise_type_id": tid, "nome": nome, "qtd": qtd, "minutos_totais": minutos}
        for tid, nome, qtd, minutos in session.execute(stmt).all()
    ]


def calendario_exercicios(session: Session, periodo: str) -> list[dict]:
    inicio, fim = _intervalo_local(periodo)
    num_dias = (fim - inicio).days + 1
    inicio_utc = datetime.combine(inicio, datetime.min.time(), tzinfo=TIMEZONE).astimezone(timezone.utc)
    fim_utc = datetime.combine(fim + timedelta(days=1), datetime.min.time(), tzinfo=TIMEZONE).astimezone(
        timezone.utc
    )

    dias = [
        {
            "data": inicio + timedelta(days=i),
            "dia_semana": NOMES_DIA[(inicio + timedelta(days=i)).weekday()],
            "checkins": [],
        }
        for i in range(num_dias)
    ]

    logs = session.execute(
        select(ExerciseLog.feito_em, ExerciseLog.duracao_min, ExerciseType.nome, User.nome)
        .join(ExerciseType, ExerciseType.id == ExerciseLog.exercise_type_id)
        .join(User, User.id == ExerciseLog.user_id)
        .where(ExerciseLog.feito_em >= inicio_utc, ExerciseLog.feito_em < fim_utc)
    ).all()
    for feito_em, duracao_min, tipo_nome, pessoa_nome in logs:
        idx = (as_utc(feito_em).astimezone(TIMEZONE).date() - inicio).days
        if 0 <= idx < num_dias:
            dias[idx]["checkins"].append(
                {"tipo": tipo_nome, "duracao_min": duracao_min, "pessoa": pessoa_nome}
            )

    return dias
