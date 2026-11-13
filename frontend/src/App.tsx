import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useAuth } from './auth/AuthProvider';
import { supabaseConfigured } from './lib/supabase';
import { obtenerModo, type ModoServidor } from './lib/modo';
import { Cargando } from './components/ui';
import { Icono, type NombreIcono } from './components/icons';
import { AuthPage } from './pages/AuthPage';
import OverviewPage from './pages/OverviewPage';
import AcademicPage from './pages/AcademicPage';
import FinancePage from './pages/FinancePage';
import TasksPage from './pages/TasksPage';
import CopilotPage from './pages/CopilotPage';
import { CopilotProvider } from './copilot/CopilotProvider';
import { CopilotWidget } from './copilot/CopilotWidget';

type ModuleId = 'overview' | 'academico' | 'finanzas' | 'tareas' | 'copiloto';

const MODULOS: { id: ModuleId; nombre: string; icono: NombreIcono }[] = [
  { id: 'overview', nombre: 'Mi espacio', icono: 'inicio' },
  { id: 'academico', nombre: 'Académico', icono: 'libro' },
  { id: 'finanzas', nombre: 'Finanzas', icono: 'billetera' },
  { id: 'tareas', nombre: 'Tareas', icono: 'check' },
  { id: 'copiloto', nombre: 'Copiloto', icono: 'destello' },
];

function ConfigPendiente() {
  return (
    <main className="auth-layout">
      <section className="auth-card">
        <h1>Configuración pendiente</h1>
        <p className="muted">
          Falta conectar el proyecto de Supabase. Define <code>VITE_SUPABASE_URL</code> y{' '}
          <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> en <code>frontend/.env.local</code> (ver{' '}
          <code>frontend/.env.example</code> y el README). Solo se usa la clave pública.
        </p>
        <p className="muted">Para trabajar en local sin Supabase, arranca el backend en modo demo (ver el README).</p>
      </section>
    </main>
  );
}

/** Estructura común: cabecera con estado del entorno, navegación con iconos y el módulo activo. */
function Shell({
  modulo,
  onCambiar,
  modo,
  cabeceraDerecha,
  children,
}: {
  modulo: ModuleId;
  onCambiar: (m: ModuleId) => void;
  modo: ModoServidor | null;
  cabeceraDerecha: ReactNode;
  children: ReactNode;
}) {
  const demo = modo?.modo === 'demo';
  return (
    <div className="app">
      <a href="#contenido" className="skip-link">Saltar al contenido</a>
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true">A</span>
          <span>AURORA AI</span>
          <span className={`entorno ${demo ? 'entorno--demo' : 'entorno--prod'}`} role="status">
            <span className="entorno__punto" aria-hidden="true" />
            {demo ? 'Demo local · SQLite' : `Entorno ${modo?.persistencia === 'supabase' ? 'Supabase' : 'de producción'}`}
          </span>
        </div>
        <div className="topbar__user">{cabeceraDerecha}</div>
      </header>

      {demo && modo?.aviso && (
        <div className="demo-banner" role="note">
          <strong>MODO DEMO LOCAL</strong>
          <span>{modo.aviso}</span>
        </div>
      )}

      <div className="layout">
        <nav className="sidebar" aria-label="Módulos">
          <ul className="sidebar__lista">
            {MODULOS.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className={`nav-item ${modulo === m.id ? 'is-active' : ''}`}
                  aria-current={modulo === m.id ? 'page' : undefined}
                  onClick={() => onCambiar(m.id)}
                >
                  <Icono nombre={m.icono} />
                  <span>{m.nombre}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <main className="content" id="contenido" tabIndex={-1}>
          {children}
        </main>
      </div>

      {/* Widget flotante: mismo estado que la página completa. No se muestra sobre la página completa. */}
      {modulo !== 'copiloto' && <CopilotWidget onExpandir={() => onCambiar('copiloto')} />}
    </div>
  );
}

function ModuloActivo({ modulo, onCambiar }: { modulo: ModuleId; onCambiar: (m: ModuleId) => void }) {
  if (modulo === 'finanzas') return <FinancePage />;
  if (modulo === 'tareas') return <TasksPage />;
  if (modulo === 'academico') return <AcademicPage />;
  if (modulo === 'copiloto') return <CopilotPage onNavigate={(m) => onCambiar(m)} />;
  return <OverviewPage onNavigate={onCambiar} />;
}

/** Modo demo: sin inicio de sesión. Solo si el SERVIDOR lo declara (DEMO_MODE, desarrollo). */
function AppDemo({ modo }: { modo: ModoServidor }) {
  const [modulo, setModulo] = useState<ModuleId>('overview');
  return (
    <CopilotProvider userKey="demo">
      <Shell
        modulo={modulo}
        onCambiar={setModulo}
        modo={modo}
        cabeceraDerecha={<span className="badge badge--demo">Sin inicio de sesión</span>}
      >
        <ModuloActivo modulo={modulo} onCambiar={setModulo} />
      </Shell>
    </CopilotProvider>
  );
}

/** Modo normal: Supabase Auth para iniciar sesión; los datos van por FastAPI. */
function AppConSesion({ modo }: { modo: ModoServidor | null }) {
  const { session, loading, signOut } = useAuth();
  const [modulo, setModulo] = useState<ModuleId>('overview');
  const [errorSesion, setErrorSesion] = useState<string | null>(null);

  const cerrarSesion = useCallback(async () => {
    setErrorSesion(null);
    try {
      await signOut();
    } catch {
      setErrorSesion('No se pudo cerrar la sesión. Intenta de nuevo.');
    }
  }, [signOut]);

  if (!supabaseConfigured) return <ConfigPendiente />;
  if (loading) return <Cargando texto="Cargando sesión…" />;
  if (!session) return <AuthPage />;

  const correo = session.user.email ?? 'Usuario';
  // userKey por cuenta: al cambiar de usuario, la conversación se reinicia. Al cerrar sesión, este árbol se desmonta.
  return (
    <CopilotProvider userKey={session.user.id}>
      <Shell
        modulo={modulo}
        onCambiar={setModulo}
        modo={modo}
        cabeceraDerecha={
          <>
            <span className="muted topbar__email" title={correo}>{correo}</span>
            <button type="button" className="btn btn--ghost" onClick={() => void cerrarSesion()}>
              Cerrar sesión
            </button>
          </>
        }
      >
        {errorSesion && <p className="alert alert--error app__alert" role="alert">{errorSesion}</p>}
        <ModuloActivo modulo={modulo} onCambiar={setModulo} />
      </Shell>
    </CopilotProvider>
  );
}

export default function App() {
  const [modo, setModo] = useState<ModoServidor | null | 'cargando'>('cargando');

  useEffect(() => {
    void obtenerModo().then(setModo);
  }, []);

  if (modo === 'cargando') return <Cargando texto="Conectando con AURORA AI…" />;
  if (modo && modo.modo === 'demo') return <AppDemo modo={modo} />;
  return <AppConSesion modo={modo} />;
}
