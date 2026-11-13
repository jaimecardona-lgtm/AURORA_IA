import { supabase } from '../lib/supabase';
import { API_BASE } from '../lib/config';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Mensajes en español para cada estado HTTP que puede devolver la API. */
const MENSAJES_POR_ESTADO: Record<number, string> = {
  401: 'Tu sesión expiró. Vuelve a iniciar sesión.',
  403: 'No tienes permiso para esta operación.',
  404: 'No encontramos ese registro.',
  409: 'Ya existe un registro con esos datos.',
  422: 'Revisa los datos ingresados.',
  501: 'Esta función no está disponible en este modo.',
  503: 'El servicio no está disponible en este momento. Intenta más tarde.',
};

/**
 * Token de Supabase Auth, si existe. En modo demo no hay cliente de Supabase:
 * la petición sale sin Authorization y el servidor decide (solo acepta eso en demo).
 */
async function accessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function mensajeDeError(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
  }
  return MENSAJES_POR_ESTADO[status] ?? 'Ocurrió un error inesperado.';
}

export async function apiRequest<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T> {
  const token = await accessToken();

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        Accept: 'application/json',
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'No hay conexión con el servidor. Revisa tu red.');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  const payload: unknown = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    throw new ApiError(response.status, mensajeDeError(response.status, payload));
  }
  return payload as T;
}

/** Query string con valores vacíos omitidos. */
export function consulta(params: Record<string, string | undefined>): string {
  const partes = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v as string)}`);
  return partes.length ? `?${partes.join('&')}` : '';
}
