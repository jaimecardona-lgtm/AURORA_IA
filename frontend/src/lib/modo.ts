import { API_BASE } from './config';

export interface ModoServidor {
  modo: 'demo' | 'produccion';
  persistencia: 'sqlite' | 'supabase';
  aviso: string | null;
}

/** Pregunta al servidor si está en modo demo. Sin red o sin respuesta válida devuelve null. */
export async function obtenerModo(): Promise<ModoServidor | null> {
  try {
    const respuesta = await fetch(`${API_BASE}/api/modo`, { headers: { Accept: 'application/json' } });
    if (!respuesta.ok) return null;
    return (await respuesta.json()) as ModoServidor;
  } catch {
    return null;
  }
}
