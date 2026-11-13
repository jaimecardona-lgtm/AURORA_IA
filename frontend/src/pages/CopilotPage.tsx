import { useRef, useState } from 'react';
import { type Inclusiones } from '../api/copilot';
import { Aviso, Badge, Cargando } from '../components/ui';
import { Icono } from '../components/icons';
import { useCopilot } from '../copilot/CopilotProvider';
import { Composer, ListaMensajes, NOMBRE_AREA, SUGERENCIAS } from '../copilot/Mensajes';

/** Por debajo de este ancho, los paneles laterales se abren como hojas flotantes (ver styles.css, Fase 07D). */
const PANTALLA_PEQUENA = '(max-width: 1000px)';
const esPantallaPequena = () => typeof window !== 'undefined' && window.matchMedia(PANTALLA_PEQUENA).matches;

/** Página completa del copiloto. Usa la misma conversación que el widget flotante (CopilotProvider). */
export default function CopilotPage({ onNavigate }: { onNavigate: (m: 'academico' | 'finanzas' | 'tareas') => void }) {
  const c = useCopilot();
  const [texto, setTexto] = useState('');
  // En escritorio ambos paneles están visibles; en tableta y móvil empiezan plegados para priorizar el chat.
  const [panelAbierto, setPanelAbierto] = useState(() => !esPantallaPequena());
  const [datosAbiertos, setDatosAbiertos] = useState(() => !esPantallaPequena());
  const campo = useRef<HTMLTextAreaElement>(null);

  if (c.errorEstado) return <Aviso tipo="error">{c.errorEstado}</Aviso>;
  if (!c.estado) return <Cargando texto="Preparando el copiloto…" />;

  const pendiente = !c.estado.configurado;
  const enviar = () => {
    if (!texto.trim()) return;
    c.enviar(texto);
    setTexto('');
  };
  const alternarArea = (k: keyof Inclusiones) => c.setIncluir({ ...c.incluir, [k]: !c.incluir[k] });

  return (
    <section aria-labelledby="titulo-copiloto" className={`copiloto copiloto--completo ${panelAbierto ? '' : 'is-sin-panel'}`}>
      <header className="copiloto__cabecera">
        <div className="copiloto__titulo">
          <button
            type="button"
            className="btn btn--ghost btn--small"
            onClick={() => setPanelAbierto((v) => !v)}
            aria-expanded={panelAbierto}
            aria-controls="panel-conversaciones"
          >
            {panelAbierto ? 'Ocultar conversaciones' : 'Mostrar conversaciones'}
          </button>
          <div>
            <p className="eyebrow">Asistente</p>
            <h1 id="titulo-copiloto">
              <Icono nombre="destello" /> AURORA Copilot
            </h1>
          </div>
        </div>
        <div className="copiloto__estado">
          <button
            type="button"
            className="btn btn--ghost btn--small copiloto__boton-datos"
            onClick={() => setDatosAbiertos((v) => !v)}
            aria-expanded={datosAbiertos}
            aria-controls="panel-datos"
          >
            Datos y sugerencias
          </button>
          {c.estado.simulado ? (
            <Badge tono="warn">SIMULADO · no es IA</Badge>
          ) : c.estado.configurado ? (
            <Badge tono="violet">OpenRouter · {c.estado.modelo}</Badge>
          ) : (
            <Badge tono="muted">Pendiente de configuración</Badge>
          )}
          <button type="button" className="btn btn--primary btn--small" onClick={c.nueva} disabled={c.pendiente}>
            Nueva conversación
          </button>
          <button type="button" className="btn btn--ghost btn--small" onClick={c.limpiar} disabled={c.pendiente || c.mensajes.length === 0}>
            Limpiar conversación
          </button>
        </div>
      </header>

      {c.estado.simulado && (
        <Aviso tipo="info">Proveedor SIMULADO de desarrollo: las respuestas son resúmenes automáticos, no inteligencia artificial.</Aviso>
      )}

      {c.aviso && (
        <Aviso tipo="error">
          {c.aviso}{' '}
          <button type="button" className="link" onClick={c.descartarAviso}>Cerrar aviso</button>
        </Aviso>
      )}

      {pendiente && (
        <section className="panel copiloto__pendiente" aria-labelledby="titulo-pendiente">
          <h2 id="titulo-pendiente">Copiloto pendiente de configuración</h2>
          <p className="muted">{c.estado.mensaje}</p>
          <p className="muted">Mientras tanto no se muestran respuestas simuladas. Puedes revisar tus datos en cada módulo.</p>
          <div className="form-actions">
            <button type="button" className="btn" onClick={() => onNavigate('academico')}>Ver Académico</button>
            <button type="button" className="btn" onClick={() => onNavigate('finanzas')}>Ver Finanzas</button>
            <button type="button" className="btn" onClick={() => onNavigate('tareas')}>Ver Tareas</button>
          </div>
        </section>
      )}

      <div className="copiloto__cuerpo">
        <aside id="panel-conversaciones" className="copiloto__conversaciones" aria-label="Conversaciones" hidden={!panelAbierto}>
          <h2>Conversaciones</h2>
          {/* Solo se afirma que está guardado cuando el servidor lo confirma (persistencia activa). */}
          <p className="muted nota-pie">
            {c.persistencia
              ? 'Guardadas en tu cuenta. Puedes continuarlas desde el widget o desde esta página.'
              : 'Solo en esta sesión del navegador. Aún no se guardan en la base de datos.'}
          </p>
          <ul className="conv-lista" aria-label="Lista de conversaciones">
            {c.conversaciones.map((conv) => (
              <li key={conv.id}>
                <button
                  type="button"
                  className={`conv-item ${conv.id === c.activaId ? 'is-activa' : ''}`}
                  aria-current={conv.id === c.activaId ? 'true' : undefined}
                  onClick={() => c.seleccionar(conv.id)}
                  disabled={c.pendiente}
                >
                  {conv.titulo}
                </button>
              </li>
            ))}
          </ul>
          {c.hayMasConversaciones && (
            <button type="button" className="btn btn--ghost btn--small" onClick={c.cargarMasConversaciones} disabled={c.pendiente}>
              Cargar más conversaciones
            </button>
          )}
        </aside>

        <div className="panel chat chat--completo">
          <ListaMensajes
            mensajes={c.mensajes}
            pendiente={c.pendiente}
            onReintentar={c.reintentar}
            vacio={c.cargando ? <Cargando texto="Cargando conversación…" /> : (
              <div className="chat__vacio">
                <p className="empty__titulo">Pregúntame sobre tus datos</p>
                <p className="muted">Empieza con una sugerencia o escribe tu pregunta. Solo leo tus registros; no modifico nada.</p>
              </div>
            )}
          />
          <Composer
            id="pregunta-copiloto"
            valor={texto}
            onCambiar={setTexto}
            onEnviar={enviar}
            pendiente={c.pendiente}
            deshabilitado={pendiente}
            maximo={c.estado.max_mensaje}
            campoRef={campo}
            placeholder={pendiente ? 'Disponible cuando el copiloto esté configurado' : 'Escribe tu pregunta. Enter envía; Shift+Enter, nueva línea.'}
          />
        </div>

        <aside id="panel-datos" className={`panel copiloto__lateral ${datosAbiertos ? '' : 'is-plegado'}`} aria-labelledby="titulo-datos">
          <h2 id="titulo-datos">Datos que puede usar</h2>
          <fieldset className="toggles">
            <legend className="visually-hidden">Áreas incluidas en la consulta</legend>
            {(['academic', 'finance', 'tasks'] as const).map((k) => (
              <label key={k} className="toggle">
                <input type="checkbox" checked={c.incluir[k]} onChange={() => alternarArea(k)} />
                <span>{NOMBRE_AREA[k]}</span>
              </label>
            ))}
          </fieldset>
          {SUGERENCIAS.map((grupo) => (
            <div key={grupo.area} className="sugerencias">
              <h3>{grupo.area}</h3>
              <ul className="chips">
                {grupo.preguntas.map((p) => (
                  <li key={p}>
                    <button
                      type="button"
                      className="chip"
                      disabled={pendiente}
                      onClick={() => {
                        setTexto(p);
                        campo.current?.focus();
                      }}
                    >
                      {p}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <p className="muted nota-pie">Las recomendaciones son orientativas y se basan solo en tus registros. Las cifras las calcula el sistema.</p>
        </aside>
      </div>
    </section>
  );
}
