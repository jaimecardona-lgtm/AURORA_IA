import { apiRequest, consulta } from './http';
import type { Subject } from './academic';
import type { CategoriaGasto } from './finance';
import type { Tarea } from './tasks';

// Espejo de backend/app/schemas/dashboard.py. Ningún valor se calcula en React.
export interface AsignaturaResumen {
  id: string;
  nombre: string;
  promedio: string | null;
  aprobado: boolean | null;
  total_notas: number;
}

export interface PanelAcademico {
  total_asignaturas: number;
  con_notas: number;
  aprobadas: number;
  reprobadas: number;
  promedio_general: string | null;
  por_asignatura: AsignaturaResumen[];
  bajo_rendimiento: AsignaturaResumen[];
  criterio_bajo_rendimiento: string;
}

export interface PanelFinanzas {
  disponible: boolean;
  anio: number;
  mes: number;
  tiene_presupuesto: boolean;
  ingreso: string | null;
  meta_ahorro: string | null;
  gastos_total: string | null;
  gastos_fijos: string | null;
  gastos_variables: string | null;
  saldo: string | null;
  ahorro_logrado: string | null;
  disponible_para_gastar: string | null;
  porcentaje_meta_ahorro: string | null;
  meta_cumplida: boolean | null;
  categorias: CategoriaGasto[];
}

export interface PanelTareas {
  disponible: boolean;
  total: number;
  completadas: number;
  pendientes: number;
  porcentaje: string | null;
  vencidas: Tarea[];
  proximas: Tarea[];
  proximas_total: number;
  pendientes_por_prioridad: { alta: number; media: number; baja: number } | null;
}

export interface Panel {
  persistencia: 'sqlite' | 'supabase';
  generado_el: string;
  academico: PanelAcademico;
  finanzas: PanelFinanzas;
  tareas: PanelTareas;
}

export const dashboardApi = {
  get: (anio?: number, mes?: number) =>
    apiRequest<Panel>('GET', `/api/dashboard${consulta({ anio: anio?.toString(), mes: mes?.toString() })}`),
};

export type { Subject };
