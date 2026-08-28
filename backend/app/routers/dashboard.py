from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from .. import crud
from ..config import TIMEZONE
from ..db import get_session

router = APIRouter(prefix="/api")

Periodo = Literal["semana", "mes", "ano", "total"]
PeriodoTempo = Literal["semana", "mes", "ano"]


def _serializar_dias(dias: list[dict]) -> list[dict]:
    return [{**d, "data": d["data"].strftime("%d/%m")} for d in dias]


# --- tarefas de casa -----------------------------------------------------------

@router.get("/ranking")
def ranking(periodo: Periodo = Query("total")):
    with get_session() as session:
        return crud.ranking_geral(session, periodo)


@router.get("/ranking/atividade/{task_type_id}")
def ranking_atividade(task_type_id: int, periodo: Periodo = Query("total")):
    with get_session() as session:
        tipos = {t.id: t for t in crud.list_task_types(session, only_active=False)}
        if task_type_id not in tipos:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        ranking_usuarios = crud.ranking_por_atividade(session, task_type_id, periodo)
        return {"tarefa": tipos[task_type_id].nome, "ranking": ranking_usuarios}


@router.get("/tempo")
def tempo(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return crud.tempo_por_atividade(session, periodo)


@router.get("/peso")
def peso(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return crud.peso_por_atividade(session, periodo)


@router.get("/tempo/pessoa")
def tempo_pessoa(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return crud.tempo_por_pessoa(session, periodo)


@router.get("/tarefas/calendario")
def tarefas_calendario(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return _serializar_dias(crud.calendario_tarefas(session, periodo))


@router.get("/agenda")
def agenda(limit: int = Query(10, ge=1, le=50)):
    with get_session() as session:
        compromissos = crud.list_upcoming_appointments(session, limit=limit)
        return [
            {
                "id": c["id"],
                "titulo": c["titulo"],
                "data_hora": c["data_hora_utc"].astimezone(TIMEZONE).isoformat(),
                "recorrente": c["recorrente"],
            }
            for c in compromissos
        ]


@router.get("/tarefas")
def tarefas():
    with get_session() as session:
        tipos = crud.list_task_types(session)
        return [
            {"id": t.id, "nome": t.nome, "peso": t.peso, "duracao_min": t.duracao_min} for t in tipos
        ]


# --- atividade física -----------------------------------------------------------

@router.get("/exercicios/tipos")
def exercicios_tipos():
    with get_session() as session:
        tipos = crud.list_exercise_types(session)
        return [{"id": t.id, "nome": t.nome} for t in tipos]


@router.get("/exercicios/ranking")
def exercicios_ranking(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return crud.ranking_exercicio_pessoa(session, periodo)


@router.get("/exercicios/tempo-por-tipo")
def exercicios_tempo_por_tipo(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return crud.tempo_por_tipo_exercicio(session, periodo)


@router.get("/exercicios/calendario")
def exercicios_calendario(periodo: PeriodoTempo = Query("semana")):
    with get_session() as session:
        return _serializar_dias(crud.calendario_exercicios(session, periodo))
