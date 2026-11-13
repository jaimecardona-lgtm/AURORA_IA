import { apiRequest, consulta } from './http';
import type { RespuestaCopiloto } from './copilot';

// Espejo de backend/app/schemas/conversaciones.py (Fase 08A). Solo se usa si el servidor informa persistencia.
export interface ConversacionRemota {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface PaginaConversaciones {
  items: ConversacionRemota[];
  siguiente: number | null;
}

export interface MensajeRemoto {
  id: string;
  cliente_id: string;
  role: 'user' | 'assistant';
  content: string;
  estado: 'completado' | 'incompleto';
  proveedor: string | null;
  modelo: string | null;
  simulado: boolean | null;
  contexto_usado: ('academic' | 'finance' | 'tasks')[];
  total_tokens: number | null;
  created_at: string;
}

export interface PaginaMensajes {
  items: MensajeRemoto[];
  siguiente: number | null;
}

export interface MensajeAGuardar {
  cliente_id: string;
  role: 'user' | 'assistant';
  content: string;
  estado?: 'completado' | 'incompleto';
  proveedor?: string | null;
  modelo?: string | null;
  simulado?: boolean | null;
  contexto_usado?: ('academic' | 'finance' | 'tasks')[];
  total_tokens?: number | null;
}

export const TAMANO_PAGINA_CONVERSACIONES = 20;
export const TAMANO_PAGINA_MENSAJES = 100;

const base = '/api/copilot/conversaciones';

export const conversacionesApi = {
  listar: (limit: number, offset: number) =>
    apiRequest<PaginaConversaciones>('GET', `${base}${consulta({ limit: String(limit), offset: String(offset) })}`),
  crear: (title?: string) =>
    apiRequest<ConversacionRemota>('POST', base, title ? { title } : {}),
  renombrar: (id: string, title: string) =>
    apiRequest<ConversacionRemota>('PATCH', `${base}/${id}`, { title }),
  eliminar: (id: string) =>
    apiRequest<void>('DELETE', `${base}/${id}${consulta({ confirmar: 'true' })}`),
  mensajes: (id: string, limit: number, offset: number) =>
    apiRequest<PaginaMensajes>('GET', `${base}/${id}/mensajes${consulta({ limit: String(limit), offset: String(offset) })}`),
  guardarMensaje: (id: string, mensaje: MensajeAGuardar) =>
    apiRequest<{ mensaje: MensajeRemoto; repetido: boolean }>('POST', `${base}/${id}/mensajes`, mensaje),
};

/** Reconstruye la respuesta del asistente a partir de lo guardado (sin inventar cifras que no se guardan). */
export function respuestaDesdeRemoto(m: MensajeRemoto): RespuestaCopiloto {
  return {
    answer: m.content,
    provider: m.proveedor === 'openrouter' ? 'openrouter' : 'simulado',
    model: m.modelo ?? '',
    simulado: m.simulado ?? false,
    context_used: m.contexto_usado,
    usage: { prompt_tokens: null, completion_tokens: null, total_tokens: m.total_tokens },
    incomplete: m.estado === 'incompleto',
    latency_ms: 0,
    prompt_version: '',
  };
}
