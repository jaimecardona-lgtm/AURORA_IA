import { apiRequest, consulta } from './http';
import type { Origen } from './academic';

// Espejo de backend/app/schemas/tasks.py.
export type Prioridad = 'alta' | 'media' | 'baja';
export type EstadoTarea = 'pendiente' | 'completada';

export interface Tarea {
  id: string;
  titulo: string;
  prioridad: Prioridad;
  prioridad_valor: number;
  estado: EstadoTarea;
  fecha_limite: string | null;
  dias_para_vencer: number | null;
  vencida: boolean;
  origen: Origen;
  created_at: string;
  updated_at: string;
}

export interface ResumenTareas {
  total: number;
  completadas: number;
  pendientes: number;
  porcentaje: string;
  vencidas: Tarea[];
  proximas: Tarea[];
}

export interface TareaEntrada {
  titulo: string;
  prioridad: Prioridad;
  estado?: EstadoTarea;
  fecha_limite?: string | null;
}

export const tasksApi = {
  list: (filtros: { estado?: string; prioridad?: string }) =>
    apiRequest<Tarea[]>('GET', `/api/tareas${consulta(filtros)}`),
  create: (tarea: TareaEntrada) => apiRequest<Tarea>('POST', '/api/tareas', tarea),
  update: (id: string, cambios: Partial<TareaEntrada>) => apiRequest<Tarea>('PATCH', `/api/tareas/${id}`, cambios),
  remove: (id: string) => apiRequest<void>('DELETE', `/api/tareas/${id}`),
  summary: () => apiRequest<ResumenTareas>('GET', '/api/tareas/resumen'),
};
