import type { ReactNode } from 'react';

export function Kpi({
  etiqueta,
  valor,
  detalle,
  tono = 'sky',
}: {
  etiqueta: string;
  valor: ReactNode;
  detalle?: string;
  tono?: 'mint' | 'sky' | 'violet' | 'orange' | 'green' | 'red';
}) {
  return (
    <article className={`kpi kpi--${tono}`}>
      <p className="kpi__etiqueta">{etiqueta}</p>
      <p className="kpi__valor">{valor}</p>
      {detalle && <p className="kpi__detalle">{detalle}</p>}
    </article>
  );
}

/** Aviso accesible: los errores usan role="alert" y el resto role="status". */
export function Aviso({ tipo, children }: { tipo: 'error' | 'ok' | 'info'; children: ReactNode }) {
  return (
    <p className={`alert alert--${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}

export function EstadoVacio({ titulo, texto, children }: { titulo: string; texto: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty__titulo">{titulo}</p>
      <p className="muted">{texto}</p>
      {children}
    </div>
  );
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {texto}
    </p>
  );
}

export function Badge({ tono, children }: { tono: 'ok' | 'bad' | 'muted' | 'demo' | 'warn' | 'violet'; children: ReactNode }) {
  return <span className={`badge badge--${tono}`}>{children}</span>;
}

/** Barra de progreso con semántica de ARIA (no depende solo del color). */
export function Progreso({ valor, etiqueta }: { valor: number; etiqueta: string }) {
  const seguro = Math.min(100, Math.max(0, valor));
  return (
    <div className="progress" role="progressbar" aria-label={etiqueta} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(seguro)}>
      <div className="progress__barra" style={{ width: `${seguro}%` }} />
    </div>
  );
}

/** Confirmación en dos pasos para acciones destructivas (sin diálogos del navegador). */
export function BotonConfirmar({
  etiqueta,
  confirmacion,
  onConfirmar,
  deshabilitado,
}: {
  etiqueta: string;
  confirmacion: string;
  onConfirmar: () => void;
  deshabilitado?: boolean;
}) {
  return (
    <details className="confirm">
      <summary className="btn btn--danger-ghost" aria-disabled={deshabilitado || undefined}>
        {etiqueta}
      </summary>
      <div className="confirm__panel">
        <p>{confirmacion}</p>
        <button type="button" className="btn btn--danger" onClick={onConfirmar} disabled={deshabilitado}>
          Sí, eliminar
        </button>
      </div>
    </details>
  );
}
