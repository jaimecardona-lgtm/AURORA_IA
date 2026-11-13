import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';

interface AuthState {
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>;
  signOut: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

/** Traduce errores de Supabase Auth a mensajes comprensibles en español. */
export function mensajeAuth(error: unknown): string {
  const texto = error instanceof Error ? error.message.toLowerCase() : '';
  if (texto.includes('invalid login credentials')) return 'Correo o contraseña incorrectos.';
  if (texto.includes('email not confirmed')) return 'Debes confirmar tu correo antes de entrar.';
  if (texto.includes('already registered') || texto.includes('already been registered')) {
    return 'Ya existe una cuenta con ese correo.';
  }
  if (texto.includes('password should be at least')) return 'La contraseña es demasiado corta (mínimo 6 caracteres).';
  if (texto.includes('rate limit') || texto.includes('too many')) return 'Demasiados intentos. Espera un momento.';
  if (texto.includes('failed to fetch') || texto.includes('network')) {
    return 'No hay conexión con el servicio de autenticación.';
  }
  return 'No se pudo completar la operación. Intenta de nuevo.';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(supabase));

  useEffect(() => {
    if (!supabase) return;
    let activo = true;

    supabase.auth.getSession().then(({ data }) => {
      if (activo) {
        setSession(data.session);
        setLoading(false);
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_evento, nueva) => {
      setSession(nueva);
    });

    return () => {
      activo = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error('Supabase no configurado');
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabase) throw new Error('Supabase no configurado');
    const { data, error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
    // Si el proyecto exige confirmación por correo, no hay sesión todavía.
    return { needsConfirmation: data.session === null };
  }, []);

  const signOut = useCallback(async () => {
    if (!supabase) return;
    // Primero se revoca globalmente. Si no hay red, supabase-js conserva la sesión local,
    // así que se cierra también en este dispositivo para que el usuario pueda salir offline.
    const { error } = await supabase.auth.signOut({ scope: 'global' });
    if (error) {
      const { error: errorLocal } = await supabase.auth.signOut({ scope: 'local' });
      if (errorLocal) throw errorLocal;
    }
  }, []);

  const requestPasswordReset = useCallback(async (email: string) => {
    if (!supabase) throw new Error('Supabase no configurado');
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin,
    });
    if (error) throw error;
  }, []);

  const value = useMemo<AuthState>(
    () => ({ session, loading, signIn, signUp, signOut, requestPasswordReset }),
    [session, loading, signIn, signUp, signOut, requestPasswordReset],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return ctx;
}
