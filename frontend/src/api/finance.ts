import { apiRequest } from './http';
import type { Origen } from './academic';

// Espejo de backend/app/schemas/finance.py. Importes como cadenas decimales.
export type TipoGasto = 'fijo' | 'variable';

export interface Presupuesto {
  anio: number;
  mes: number;
  ingreso: string;
  meta_ahorro: string;
  origen: Origen;
  gastos_total: string;
  saldo: string;
  meta_cumplida: boolean;
}

export interface Gasto {
  id: string;
  descripcion: string;
  categoria: string;
  monto: string;
  tipo: TipoGasto;
  fecha: string;
  origen: Origen;
  created_at: string;
  updated_at: string;
}

export interface CategoriaGasto {
  categoria: string;
  total: string;
  porcentaje: string;
}

export interface PresupuestoDetalle extends Presupuesto {
  gastos_fijos: string;
  gastos_variables: string;
  disponible_para_gastar: string;
  ahorro_logrado: string;
  categorias: CategoriaGasto[];
  gastos: Gasto[];
}

export interface GastoEntrada {
  descripcion: string;
  categoria: string;
  monto: number;
  tipo: TipoGasto;
  fecha: string;
}

const ruta = (anio: number, mes: number) => `/api/finanzas/presupuestos/${anio}/${mes}`;

export const financeApi = {
  listBudgets: () => apiRequest<Presupuesto[]>('GET', '/api/finanzas/presupuestos'),
  defineBudget: (anio: number, mes: number, ingreso: number, metaAhorro: number) =>
    apiRequest<Presupuesto>('PUT', ruta(anio, mes), { ingreso, meta_ahorro: metaAhorro }),
  getBudget: (anio: number, mes: number) => apiRequest<PresupuestoDetalle>('GET', ruta(anio, mes)),
  addExpense: (anio: number, mes: number, gasto: GastoEntrada) =>
    apiRequest<Gasto>('POST', `${ruta(anio, mes)}/gastos`, gasto),
  updateExpense: (id: string, cambios: Partial<GastoEntrada>) =>
    apiRequest<Gasto>('PATCH', `/api/finanzas/gastos/${id}`, cambios),
  deleteExpense: (id: string) => apiRequest<void>('DELETE', `/api/finanzas/gastos/${id}`),
};
