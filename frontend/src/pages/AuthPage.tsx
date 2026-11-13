import { useState, type FormEvent } from 'react';
import { mensajeAuth, useAuth } from '../auth/AuthProvider';

type Modo = 'ingresar' | 'registrarse' | 'recuperar';

export function AuthPage() {
  const { signIn, signUp, requestPasswordReset } = useAuth();
  const [modo, setModo] = useState<Modo>('ingresar');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const cambiarModo = (nuevo: Modo) => {
    setModo(nuevo);
    setError(null);
    setAviso(null);
  };

  const validar = (): string | null => {
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) return 'Ingresa un correo válido.';
    if (modo !== 'recuperar' && password.length < 6) return 'La contraseña debe tener al menos 6 caracteres.';
    return null;
  };

  const onSubmit = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setError(null);
    setAviso(null);
    const problema = validar();
    if (problema) {
      setError(problema);
      return;
    }

    setEnviando(true);
    try {
      if (modo === 'ingresar') {
        await signIn(email.trim(), password);
      } else if (modo === 'registrarse') {
        const { needsConfirmation } = await signUp(email.trim(), password);
        setAviso(
          needsConfirmation
            ? 'Cuenta creada. Revisa tu correo para confirmarla y luego inicia sesión.'
            : 'Cuenta creada. Ya puedes usar el espacio de trabajo.',
        );
        setModo('ingresar');
        setPassword('');
      } else {
        await requestPasswordReset(email.trim());
        setAviso('Si el correo está registrado, recibirás un enlace para restablecer la contraseña.');
      }
    } catch (err) {
      setError(mensajeAuth(err));
    } finally {
      setEnviando(false);
    }
  };

  const titulo = {
    ingresar: 'Inicia sesión',
    registrarse: 'Crea tu cuenta',
    recuperar: 'Recupera tu contraseña',
  }[modo];

  return (
    <main className="auth-layout">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="brand brand--large">
          <span className="brand__mark" aria-hidden="true">A</span>
          <span>AURORA AI</span>
        </div>
        <p className="eyebrow">Intelligent Student Workspace</p>
        <h1 id="auth-title">{titulo}</h1>

        <form className="stack" onSubmit={onSubmit} noValidate aria-busy={enviando}>
          <label className="field">
            <span>Correo electrónico</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          {modo !== 'recuperar' && (
            <label className="field">
              <span>Contraseña</span>
              <input
                type="password"
                autoComplete={modo === 'registrarse' ? 'new-password' : 'current-password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </label>
          )}

          {error && <p className="alert alert--error" role="alert">{error}</p>}
          {aviso && <p className="alert alert--ok" role="status">{aviso}</p>}

          <button className="btn btn--primary" type="submit" disabled={enviando}>
            {enviando && <span className="spinner" aria-hidden="true" />}
            {enviando
              ? 'Procesando…'
              : modo === 'ingresar'
                ? 'Entrar'
                : modo === 'registrarse'
                  ? 'Crear cuenta'
                  : 'Enviar enlace'}
          </button>
        </form>

        <nav className="auth-links" aria-label="Opciones de acceso">
          {modo !== 'ingresar' && (
            <button type="button" className="link" onClick={() => cambiarModo('ingresar')}>
              Ya tengo cuenta
            </button>
          )}
          {modo !== 'registrarse' && (
            <button type="button" className="link" onClick={() => cambiarModo('registrarse')}>
              Crear cuenta nueva
            </button>
          )}
          {modo !== 'recuperar' && (
            <button type="button" className="link" onClick={() => cambiarModo('recuperar')}>
              Olvidé mi contraseña
            </button>
          )}
        </nav>
      </section>
    </main>
  );
}
