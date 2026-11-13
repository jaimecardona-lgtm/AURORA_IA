import { useEffect, useState } from 'react';
import { dashboardApi, type Panel } from '../api/dashboard';
import { ApiError } from '../api/http';
import { BarrasHorizontales, Dona } from '../components/charts';
import { Icono, type NombreIcono } from '../components/icons';
import { Aviso, Badge, Cargando, EstadoVacio, Kpi, Progreso } from '../components/ui';
import { formatCop, formatFecha, formatNota, formatPorcentaje, mesActual } from '../lib/format';

type Modulo = 'academico' | 'finanzas' | 'tareas' | 'copiloto';

function errorDe(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo cargar el panel. Intenta de nuevo.';
}

function periodoTexto(anio: number, mes: number): string {
  return new Date(anio, mes - 1, 1).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });
}

function Acceso({ icono, titulo, texto, onClick }: { icono: NombreIcono; titulo: string; texto: string; onClick: () => void }) {
  return (
    <button type="button" className="btn btn--ghost acceso" onClick={onClick}>
      <Icono nombre={icono} /> <span>{titulo}</span>
      <span className="muted acceso__texto">{texto}</span>
      <Icono nombre="flecha" size={16} />
    </button>
  );
}

export default function OverviewPage({ onNavigate }: { onNavigate: (m: Modulo) => void }) {
  const actual = mesActual();
  const [periodo, setPeriodo] = useState(`${actual.anio}-${String(actual.mes).padStart(2, '0')}`);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const [anio, mes] = periodo.split('-').map(Number);
    let activo = true;
    setError(null);
    dashboardApi
      .get(anio, mes)
      .then((p) => activo && setPanel(p))
      .catch((e) => activo && setError(errorDe(e)));
    return () => {
      activo = false;
    };
  }, [periodo]);

  if (error && !panel) return <Aviso tipo="error">{error}</Aviso>;
  if (!panel) return <Cargando texto="Preparando tu espacio…" />;

  const { academico: ac, finanzas: fi, tareas: ta } = panel;
  const conFinanzas = fi.disponible && fi.tiene_presupuesto;
  const pendientesPrioridad = ta.pendientes_por_prioridad;
  const maxPrioridad = Math.max(1, pendientesPrioridad?.alta ?? 0, pendientesPrioridad?.media ?? 0, pendientesPrioridad?.baja ?? 0);
  const porcentajeMeta = fi.porcentaje_meta_ahorro !== null ? Number(fi.porcentaje_meta_ahorro) : null;

  return (
    <section aria-labelledby="titulo-overview" className="module overview">
      <header className="module__header">
        <div>
          <p className="eyebrow">Mi espacio</p>
          <h1 id="titulo-overview">Vista general</h1>
          <p className="muted">
            Indicadores reales de tus tres áreas. Las cifras las calcula el servidor con los motores de dominio.
          </p>
        </div>
        <div className="field field--compact">
          <label htmlFor="periodo-overview">Mes de finanzas</label>
          <input id="periodo-overview" type="month" value={periodo} onChange={(e) => e.target.value && setPeriodo(e.target.value)} />
        </div>
      </header>

      {error && <Aviso tipo="error">{error}</Aviso>}

      <div className="kpis kpis--seis">
        <Kpi
          etiqueta="Promedio general"
          valor={formatNota(ac.promedio_general)}
          tono="violet"
          detalle={ac.con_notas ? `${ac.con_notas} asignaturas con notas` : 'Sin notas registradas'}
        />
        <Kpi
          etiqueta="Asignaturas aprobadas"
          valor={`${ac.aprobadas} / ${ac.con_notas}`}
          tono="green"
          detalle={ac.reprobadas ? `${ac.reprobadas} con bajo rendimiento` : 'Ninguna reprobada'}
        />
        <Kpi
          etiqueta="Saldo del mes"
          valor={fi.saldo !== null ? formatCop(fi.saldo) : '—'}
          tono={fi.saldo !== null && Number(fi.saldo) < 0 ? 'red' : 'sky'}
          detalle={fi.tiene_presupuesto ? `Disponible para gastar ${formatCop(fi.disponible_para_gastar ?? 0)}` : 'Sin presupuesto este mes'}
        />
        <Kpi
          etiqueta="Meta de ahorro"
          valor={porcentajeMeta !== null ? formatPorcentaje(porcentajeMeta) : '—'}
          tono="mint"
          detalle={
            porcentajeMeta === null
              ? 'Define una meta para medirla'
              : fi.meta_cumplida
                ? `Meta cumplida: ahorro de ${formatCop(fi.ahorro_logrado ?? 0)}`
                : `Llevas ${formatCop(fi.ahorro_logrado ?? 0)} de ${formatCop(fi.meta_ahorro ?? 0)}`
          }
        />
        <Kpi
          etiqueta="Tareas pendientes"
          valor={ta.disponible ? ta.pendientes : '—'}
          tono="orange"
          detalle={ta.disponible ? `${ta.completadas} completadas de ${ta.total}` : 'Disponible con SQLite'}
        />
        <Kpi
          etiqueta="Próximas a vencer"
          valor={ta.disponible ? ta.proximas_total : '—'}
          tono="red"
          detalle={ta.disponible ? `${ta.vencidas.length} vencidas · ventana de 7 días` : 'Disponible con SQLite'}
        />
      </div>

      <div className="grid-overview">
        <div className="panel">
          <div className="panel__cabecera">
            <h2>Rendimiento por asignatura</h2>
            <Badge tono="muted">Escala 0–5</Badge>
          </div>
          {ac.por_asignatura.some((a) => a.promedio !== null) ? (
            <>
              <BarrasHorizontales
                titulo="Promedio por asignatura"
                maximo={5}
                items={ac.por_asignatura
                  .filter((a) => a.promedio !== null)
                  .map((a) => ({ etiqueta: a.nombre, valor: Number(a.promedio), texto: formatNota(a.promedio) }))}
              />
              <p className="muted nota-pie">
                Aprobación desde 3,00. {ac.criterio_bajo_rendimiento} Todas las notas pesan igual; las ponderaciones aún no están implementadas.
              </p>
            </>
          ) : (
            <EstadoVacio titulo="Sin notas aún" texto="Registra notas en Académico para ver el rendimiento por asignatura.">
              <button type="button" className="btn btn--primary" onClick={() => onNavigate('academico')}>Ir a Académico</button>
            </EstadoVacio>
          )}
        </div>

        <div className="panel">
          <div className="panel__cabecera">
            <h2>Distribución de gastos</h2>
            <span className="muted">{periodoTexto(fi.anio, fi.mes)}</span>
          </div>
          {!fi.disponible ? (
            <EstadoVacio titulo="No disponible" texto="Las finanzas se conectan con SQLite en esta fase." />
          ) : fi.categorias.length === 0 ? (
            <EstadoVacio titulo="Sin gastos este mes" texto="Cuando registres gastos verás su distribución por categoría.">
              <button type="button" className="btn btn--primary" onClick={() => onNavigate('finanzas')}>Ir a Finanzas</button>
            </EstadoVacio>
          ) : (
            <Dona
              titulo="Gasto por categoría"
              items={fi.categorias.map((c) => ({ etiqueta: c.categoria, porcentaje: Number(c.porcentaje), texto: `${formatPorcentaje(c.porcentaje)} · ${formatCop(c.total)}` }))}
            />
          )}
        </div>

        <div className="panel">
          <div className="panel__cabecera">
            <h2>Progreso de tareas</h2>
            <strong>{ta.disponible ? formatPorcentaje(ta.porcentaje ?? '0') : '—'}</strong>
          </div>
          {ta.disponible ? (
            <>
              <Progreso valor={Number(ta.porcentaje ?? 0)} etiqueta="Porcentaje de tareas completadas" />
              <p className="muted">{ta.completadas} de {ta.total} tareas completadas.</p>
              {pendientesPrioridad && (
                <BarrasHorizontales
                  titulo="Pendientes por prioridad"
                  maximo={maxPrioridad}
                  items={[
                    { etiqueta: 'Alta', valor: pendientesPrioridad.alta, texto: String(pendientesPrioridad.alta) },
                    { etiqueta: 'Media', valor: pendientesPrioridad.media, texto: String(pendientesPrioridad.media) },
                    { etiqueta: 'Baja', valor: pendientesPrioridad.baja, texto: String(pendientesPrioridad.baja) },
                  ]}
                />
              )}
            </>
          ) : (
            <EstadoVacio titulo="No disponible" texto="El gestor de tareas se conecta con SQLite en esta fase." />
          )}
        </div>

        <div className="panel">
          <div className="panel__cabecera">
            <h2>Próximas tareas</h2>
            <button type="button" className="btn btn--ghost btn--small" onClick={() => onNavigate('tareas')}>Ver todas</button>
          </div>
          {!ta.disponible ? (
            <p className="muted">Sin datos de tareas con esta persistencia.</p>
          ) : ta.vencidas.length === 0 && ta.proximas.length === 0 ? (
            <EstadoVacio titulo="Nada urgente" texto="No tienes tareas vencidas ni próximas a vencer." />
          ) : (
            <ul className="list" aria-label="Tareas vencidas y próximas">
              {[...ta.vencidas, ...ta.proximas].map((t) => (
                <li key={t.id} className={`list__item list__item--static prioridad prioridad--${t.prioridad}`}>
                  <span className="list__titulo">{t.titulo}</span>
                  <span className="list__meta">
                    <Badge tono={t.vencida ? 'bad' : 'warn'}>{t.vencida ? 'Vencida' : 'Próxima'}</Badge>
                    {t.fecha_limite && <span>{formatFecha(t.fecha_limite)}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="panel">
          <h2>Estado financiero</h2>
          {!fi.disponible ? (
            <p className="muted">Sin datos financieros con esta persistencia.</p>
          ) : !conFinanzas ? (
            <EstadoVacio titulo="Sin presupuesto este mes" texto="Define el ingreso del mes para ver tu estado financiero.">
              <button type="button" className="btn btn--primary" onClick={() => onNavigate('finanzas')}>Definir presupuesto</button>
            </EstadoVacio>
          ) : (
            <dl className="resumen-dl">
              <div><dt>Ingreso</dt><dd>{formatCop(fi.ingreso ?? 0)}</dd></div>
              <div><dt>Gasto acumulado</dt><dd>{formatCop(fi.gastos_total ?? 0)}</dd></div>
              <div><dt>Fijos / variables</dt><dd>{formatCop(fi.gastos_fijos ?? 0)} / {formatCop(fi.gastos_variables ?? 0)}</dd></div>
              <div><dt>Saldo</dt><dd>{formatCop(fi.saldo ?? 0)}</dd></div>
              <div><dt>Meta de ahorro</dt><dd>{formatCop(fi.meta_ahorro ?? 0)} {fi.meta_cumplida ? <Badge tono="ok">Cumplida</Badge> : <Badge tono="warn">Pendiente</Badge>}</dd></div>
            </dl>
          )}
        </div>

        <div className="panel">
          <h2>Accesos</h2>
          <div className="accesos">
            <Acceso icono="libro" titulo="Académico" texto="Notas y promedios" onClick={() => onNavigate('academico')} />
            <Acceso icono="billetera" titulo="Finanzas" texto="Presupuesto y gastos" onClick={() => onNavigate('finanzas')} />
            <Acceso icono="tareas" titulo="Tareas" texto="Prioridades y fechas" onClick={() => onNavigate('tareas')} />
          </div>
        </div>

        <div className="panel panel--copiloto" aria-label="Copiloto de IA">
          <div className="panel__cabecera">
            <h2><Icono nombre="destello" /> AURORA Copilot</h2>
            <Badge tono="violet">Solo lectura</Badge>
          </div>
          <p className="muted">
            Pregunta sobre tus notas, tu presupuesto o tus tareas. El asistente analiza tus datos registrados y no modifica nada.
          </p>
          <button type="button" className="btn btn--primary" onClick={() => onNavigate('copiloto')}>Abrir copiloto</button>
        </div>
      </div>
    </section>
  );
}
