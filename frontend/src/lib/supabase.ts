import { createClient, type SupabaseClient } from '@supabase/supabase-js';

// Cliente de Supabase usado EXCLUSIVAMENTE para Auth (registro, login, logout,
// recuperación y lectura de la sesión/token). Los datos de negocio no se leen
// ni escriben desde el navegador: van por FastAPI.
const url = import.meta.env.VITE_SUPABASE_URL?.trim() ?? '';
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() ?? '';

export const supabaseConfigured = Boolean(url && publishableKey);

export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url, publishableKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
