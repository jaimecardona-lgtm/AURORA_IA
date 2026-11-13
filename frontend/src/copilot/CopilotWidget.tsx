import { useEffect, useRef, useState } from 'react';
import { Icono } from '../components/icons';
import { useCopilot } from './CopilotProvider';
import { Composer, ListaMensajes, SUGERENCIAS } from './Mensajes';

/**
 * Widget flotante «Habla con AURORA ✦». Se renderiza dentro del layout autenticado.
 * Comparte la conversación con la página completa a través de CopilotProvider.
 */
export function CopilotWidget({ onExpandir }: { onExpandir: () => void }) {
  const c = useCopilot();
  const [texto, setTexto] = useState('');
  const botonRef = useRef<HTMLButtonElement>(null);
  const campoRef = useRef<HTMLTextAreaElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // Gestión de foco: al abrir, al campo; al cerrar, al botón. El foco se mueve DESPUÉS de que el
  // elemento exista en el DOM (el botón se monta al cerrar el panel).
  const abrir = () => c.setAbierto(true);
  const cerrar = () => c.setAbierto(false);
  const estabaAbierto = useRef(c.abierto);

  useEffect(() => {
    if (c.abierto) campoRef.current?.focus();
    else if (estabaAbierto.current) botonRef.current?.focus();
    estabaAbierto.current = c.abierto;
  }, [c.abierto]);

  // Escape cierra el panel cuando el foco está dentro.
  useEffect(() => {
    if (!c.abierto) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cerrar();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [c.abierto]);

  if (!c.estado) return null; // mientras carga, no mostrar un widget vacío

  const pendiente = !c.estado.configurado;
  const enviar = () => {
    if (!texto.trim()) return;
    c.enviar(texto);
    setTexto('');
  };

  return (
    <>
      {!c.abierto && (
        <button
          ref={botonRef}
          type="button"
          className="copiloto-flotante"
          onClick={abrir}
          aria-expanded={false}
          aria-controls="widget-aurora"
          aria-label="Habla con AURORA"
        >
          <Icono nombre="destello" size={18} />
          <span className="copiloto-flotante__texto">Habla con AURORA</span>
          <span aria-hidden="true" className="copiloto-flotante__marca">✦</span>
        </button>
      )}

      {c.abierto && (
        <div
          ref={panelRef}
          id="widget-aurora"
          className="widget-aurora"
          role="dialog"
          aria-modal="false"
          aria-labelledby="titulo-widget"
        >
          <header className="widget-aurora__cabecera">
            <div className="widget-aurora__marca">
              <span className="brand__mark" aria-hidden="true">A</span>
              <div>
                <h2 id="titulo-widget">Habla con AURORA ✦</h2>
                <p className="muted">
                  {c.estado.simulado ? 'Simulado · no es IA' : c.estado.configurado ? `OpenRouter · ${c.estado.modelo}` : 'Pendiente de configuración'}
                </p>
              </div>
            </div>
            <div className="widget-aurora__acciones">
              <button type="button" className="btn btn--ghost btn--small" onClick={() => { c.setAbierto(false); onExpandir(); }} aria-label="Abrir el chat completo">
                Chat completo
              </button>
              <button type="button" className="btn btn--ghost btn--small" onClick={c.nueva} disabled={c.pendiente} aria-label="Nueva conversación">
                Nueva
              </button>
              <button type="button" className="btn btn--ghost btn--small" onClick={c.limpiar} disabled={c.pendiente || c.mensajes.length === 0} aria-label="Limpiar conversación">
                Limpiar
              </button>
              <button type="button" className="btn btn--ghost btn--small" onClick={cerrar} aria-label="Cerrar el asistente">
                ✕
              </button>
            </div>
          </header>

          {pendiente ? (
            <p className="widget-aurora__aviso muted" role="status">
              El copiloto aún no está configurado. No se muestran respuestas simuladas.
            </p>
          ) : null}

          <ListaMensajes
            mensajes={c.mensajes}
            pendiente={c.pendiente}
            onReintentar={c.reintentar}
            vacio={
              <div className="widget-aurora__bienvenida">
                <p>Hola, soy AURORA. Puedo revisar tus notas, tu presupuesto y tus tareas. ¿Qué quieres revisar?</p>
                <ul className="chips">
                  {SUGERENCIAS.flatMap((g) => g.preguntas.slice(0, 1)).map((p) => (
                    <li key={p}>
                      <button type="button" className="chip" disabled={pendiente} onClick={() => setTexto(p)}>
                        {p}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            }
          />

          <Composer
            id="pregunta-widget"
            valor={texto}
            onCambiar={setTexto}
            onEnviar={enviar}
            pendiente={c.pendiente}
            deshabilitado={pendiente}
            maximo={c.estado.max_mensaje}
            campoRef={campoRef}
            placeholder={pendiente ? 'Disponible cuando el copiloto esté configurado' : 'Escribe tu pregunta…'}
          />
        </div>
      )}
    </>
  );
}
