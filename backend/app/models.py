from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), unique=True)
    telegram_user_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    task_logs: Mapped[list["TaskLog"]] = relationship(back_populates="user")


class TaskType(Base):
    __tablename__ = "task_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    peso: Mapped[int] = mapped_column(Integer, default=1)
    duracao_min: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    logs: Mapped[list["TaskLog"]] = relationship(back_populates="task_type")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    done_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    duracao_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task_type: Mapped["TaskType"] = relationship(back_populates="logs")
    user: Mapped["User"] = relationship(back_populates="task_logs")


class TaskAssignment(Base):
    """Tarefa planejada pra um dia específico, ainda não necessariamente concluída."""

    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type_id: Mapped[int] = mapped_column(ForeignKey("task_types.id"))
    data: Mapped[date] = mapped_column(Date)
    recorrencia_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorrencia_intervalo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task_type: Mapped["TaskType"] = relationship()


class ExerciseType(Base):
    __tablename__ = "exercise_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    duracao_min: Mapped[int] = mapped_column(Integer, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    logs: Mapped[list["ExerciseLog"]] = relationship(back_populates="exercise_type")


class ExerciseLog(Base):
    """Um checkin de exercício — duração é por checkin, não pelo tipo (varia a cada vez)."""

    __tablename__ = "exercise_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_type_id: Mapped[int] = mapped_column(ForeignKey("exercise_types.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    duracao_min: Mapped[int] = mapped_column(Integer)
    feito_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    exercise_type: Mapped["ExerciseType"] = relationship(back_populates="logs")
    user: Mapped["User"] = relationship()


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorrencia_tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorrencia_intervalo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
