import { useEffect, useRef, type KeyboardEvent, type ReactNode, type RefObject } from 'react';
import { Badge } from '../components/ui';
import type { Mensaje } from './CopilotProvider';

export const NOMBRE_AREA: Record<string, string> = { academic: 'Académico', finance: 'Finanzas', tasks: 'Tareas' };

export const SUGERENCIAS: { area: string; preguntas: string[] }[] = [
  { area: 'Académico', preguntas: ['¿Cuál es mi promedio académico?', '¿Qué asignaturas requieren más atención?', '¿Cuánto necesito en la próxima evaluación para llegar a 4,0?'] },
  { area: 'Finanzas', preguntas: ['¿En qué categoría estoy gastando más?', '¿Voy cumpliendo mi meta de ahorro?', '¿Qué gastos debería revisar primero?'] },
  { area: 'Tareas', preguntas: ['¿Qué tareas son más urgentes?', '¿Qué actividades están vencidas?', '¿Cómo podría organizar mi semana?'] },
];

/** Negritas **así** dentro de un texto, sin HTML. */
function negritas(texto: string): ReactNode[] {
  return texto.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith('**') && parte.endsWith('**') && parte.length > 4 ? <strong key={i}>{parte.slice(2, -2)}</strong> : parte,
  );
}

/**
 * Renderizado seguro: el texto del modelo se muestra como TEXTO. Solo se interpretan párrafos,
 * listas con guion y **negritas**. Nunca se inserta HTML (sin dangerouslySetInnerHTML).
 */
export function Texto({ contenido }: { contenido: string }) {
  const bloques = contenido.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {bloques.map((bloque, i) => {
        const lineas = bloque.split('\n').map((l) => l.trim());
        const esLista = lineas.every((l) => /^[-•]\s+/.test(l) || l === '');
        if (esLista) {
          return (
            <ul key={i} className="chat__lista">
              {lineas.filter(Boolean).map((l, j) => (
                <li key={j}>{negritas(l.replace(/^[-•]\s+/, ''))}</li>
              ))}
            </ul>
          );
        }
        return <p key={i}>{lineas.map((l, j) => <span key={j}>{j > 0 && <br />}{negritas(l)}</span>)}</p>;
      })}
    </>
  );
}

export function ListaMensajes({
  mensajes,
  pendiente,
  onReintentar,
  vacio,
}: {
  mensajes: Mensaje[];
  pendiente: boolean;
  onReintentar: (id: number) => void;
  vacio?: ReactNode;
}) {
  const fin = useRef<HTMLDivElement>(null);
  useEffect(() => {
    fin.current?.scrollIntoView({ block: 'end' });
  }, [mensajes.length, pendiente]);

  return (
    <div className="chat__log" role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversación con AURORA Copilot">
      {mensajes.length === 0 && vacio}
      {mensajes.map((m) => {
        if (m.rol === 'user') {
          return (
            <div key={m.id} className="chat__burbuja chat__burbuja--usuario">
              <p>{m.texto}</p>
            </div>
          );
        }
        if (m.rol === 'error') {
          return (
            <div key={m.id} className="chat__burbuja chat__burbuja--error" role="alert">
              <p>{m.texto}</p>
              <button type="button" className="btn btn--small" onClick={() => onReintentar(m.id)} disabled={pendiente}>
                Reintentar
              </button>
            </div>
          );
        }
        return (
          <article key={m.id} className="chat__burbuja chat__burbuja--asistente" aria-label="Respuesta del copiloto">
            <div className="chat__origen">
              {m.respuesta.simulado ? (
                <Badge tono="warn">Simulado · no es IA</Badge>
              ) : (
                <Badge tono="violet">Generado por OpenRouter · {m.respuesta.model}</Badge>
              )}
              {m.respuesta.incomplete && <Badge tono="warn">Respuesta cortada por límite</Badge>}
            </div>
            <Texto contenido={m.texto} />
            <p className="chat__datos">
              {m.respuesta.context_used.length
                ? `Datos usados: ${m.respuesta.context_used.map((c) => NOMBRE_AREA[c]).join(', ')}`
                : 'Sin datos de contexto en esta consulta.'}
              {m.respuesta.usage.total_tokens !== null && ` · ${m.respuesta.usage.total_tokens} tokens`}
            </p>
          </article>
        );
      })}
      {pendiente && (
        <p className="chat__pensando" role="status">
          <span className="spinner" aria-hidden="true" /> AURORA está generando la respuesta…
        </p>
      )}
      <div ref={fin} />
    </div>
  );
}

export function Composer({
  id,
  valor,
  onCambiar,
  onEnviar,
  pendiente,
  deshabilitado,
  maximo,
  campoRef,
  placeholder,
}: {
  id: string;
  valor: string;
  onCambiar: (v: string) => void;
  onEnviar: () => void;
  pendiente: boolean;
  deshabilitado: boolean;
  maximo: number;
  campoRef?: RefObject<HTMLTextAreaElement | null>;
  placeholder: string;
}) {
  const onTeclas = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!pendiente && !deshabilitado && valor.trim()) onEnviar();
    }
  };
  return (
    <form
      className="chat__form"
      onSubmit={(e) => {
        e.preventDefault();
        if (!pendiente && !deshabilitado && valor.trim()) onEnviar();
      }}
      noValidate
    >
      <label className="visually-hidden" htmlFor={id}>Tu pregunta</label>
      <textarea
        id={id}
        ref={campoRef}
        value={valor}
        onChange={(e) => onCambiar(e.target.value)}
        onKeyDown={onTeclas}
        rows={2}
        maxLength={maximo}
        disabled={deshabilitado}
        placeholder={placeholder}
        aria-describedby={`contador-${id}`}
      />
      <div className="chat__pie">
        <span id={`contador-${id}`} className="muted">{valor.length}/{maximo}</span>
        <button type="submit" className="btn btn--primary" disabled={deshabilitado || pendiente || !valor.trim()}>
          Enviar
        </button>
      </div>
    </form>
  );
}
