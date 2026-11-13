"""DTO del módulo financiero (presupuesto mensual en COP).

extra="forbid": el cliente no puede enviar user_id ni campos no previstos.
Las reglas de importes viven en app.core.budget; aquí solo se da forma a los datos.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)

Origen = Literal["real", "demo"]
TipoGasto = Literal["fijo", "variable"]
Anio = Annotated[int, Field(ge=2000, le=2100)]
Mes = Annotated[int, Field(ge=1, le=12)]


class BudgetIn(BaseModel):
    model_config = _STRICT
    ingreso: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    meta_ahorro: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] = Decimal("0")


class ExpenseIn(BaseModel):
    model_config = _STRICT
    descripcion: Annotated[str, Field(min_length=1, max_length=200)]
    categoria: Annotated[str, Field(min_length=1, max_length=60)]
    monto: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
    tipo: TipoGasto
    fecha: date


class ExpenseUpdate(BaseModel):
    model_config = _STRICT
    descripcion: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    categoria: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    monto: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] | None = None
    tipo: TipoGasto | None = None
    fecha: date | None = None

    @model_validator(mode="after")
    def _al_menos_un_campo(self) -> "ExpenseUpdate":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("Indica al menos un campo para actualizar.")
        return self


class ExpenseOut(BaseModel):
    id: UUID
    descripcion: str
    categoria: str
    monto: Decimal
    tipo: TipoGasto
    fecha: date
    origen: Origen = "real"
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ExpenseOut":
        return cls(
            id=row["id"],
            descripcion=row["descripcion"],
            categoria=row["categoria"],
            monto=Decimal(str(row["monto"])).quantize(Decimal("0.01")),
            tipo=row["tipo"],
            fecha=row["fecha"],
            origen=row.get("origen", "real"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class CategoryShareOut(BaseModel):
    categoria: str
    total: Decimal
    porcentaje: Decimal


class BudgetOut(BaseModel):
    anio: int
    mes: int
    ingreso: Decimal
    meta_ahorro: Decimal
    origen: Origen = "real"
    gastos_total: Decimal
    saldo: Decimal
    meta_cumplida: bool


class BudgetDetailOut(BudgetOut):
    gastos_fijos: Decimal
    gastos_variables: Decimal
    disponible_para_gastar: Decimal
    ahorro_logrado: Decimal
    categorias: list[CategoryShareOut]
    gastos: list[ExpenseOut]
