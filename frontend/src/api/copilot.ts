import { apiRequest } from './http';

// Espejo de backend/app/schemas/copilot.py. El servidor construye el contexto; el navegador solo envía la pregunta.
export interface EstadoCopiloto {
  configurado: boolean;
  proveedor: 'openrouter' | 'simulado';
  modelo: string | null;
  simulado: boolean;
  modo: 'demo' | 'produccion';
  max_mensaje: number;
  max_turnos_historial: number;
  mensaje: string;
  /** true solo si el servidor guarda las conversaciones en la cuenta del usuario (migración 08A aplicada). */
  persistencia: boolean;
}

export interface Turno {
  role: 'user' | 'assistant';
  content: string;
}

export interface Inclusiones {
  academic: boolean;
  finance: boolean;
  tasks: boolean;
}

export interface RespuestaCopiloto {
  answer: string;
  provider: 'openrouter' | 'simulado';
  model: string;
  simulado: boolean;
  context_used: ('academic' | 'finance' | 'tasks')[];
  usage: { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null };
  incomplete: boolean;
  latency_ms: number;
  prompt_version: string;
}

export const copilotApi = {
  estado: () => apiRequest<EstadoCopiloto>('GET', '/api/copilot/estado'),
  chat: (message: string, history: Turno[], include: Inclusiones) =>
    apiRequest<RespuestaCopiloto>('POST', '/api/copilot/chat', { message, history, include_context: include }),
};
