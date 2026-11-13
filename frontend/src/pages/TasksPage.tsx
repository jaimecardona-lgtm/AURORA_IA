import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { tasksApi, type EstadoTarea, type Prioridad, type ResumenTareas, type Tarea } from '../api/tasks';
import { ApiError } from '../api/http';
import { Aviso, Badge, BotonConfirmar, Cargando, EstadoVacio, Kpi, Progreso } from '../components/ui';
import { formatFecha, formatPorcentaje } from '../lib/format';

const TITULO_MAX = 200;
const PRIORIDADES: Prioridad[] = ['alta', 'media', 'baja'];

function errorDe(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación. Intenta de nuevo.';
}

function textoVencimiento(t: Tarea): string {
  if (t.fecha_limite === null || t.dias_para_vencer === null) return 'Sin fecha límite';
  if (t.estado === 'completada') return `Fecha límite ${formatFecha(t.fecha_limite)}`;
  if (t.dias_para_vencer < 0) {
    const dias = Math.abs(t.dias_para_vencer);
    return `Vencida hace ${dias} ${dias === 1 ? 'día' : 'días'} (${formatFecha(t.fecha_limite)})`;
  }
  if (t.dias_para_vencer === 0) return `Vence hoy (${formatFecha(t.fecha_limite)})`;
  return `Vence en ${t.dias_para_vencer} ${t.dias_para_vencer === 1 ? 'día' : 'días'} (${formatFecha(t.fecha_limite)})`;
}

const toneDePrioridad = (p: Prioridad) => (p === 'alta' ? 'bad' : p === 'media' ? 'warn' : 'muted');

export default function TasksPage() {
  const [tareas, setTareas] = useState<Tarea[] | null>(null);
  const [resumen, setResumen] = useState<ResumenTareas | null>(null);
  const [filtroEstado, setFiltroEstado] = useState<'' | EstadoTarea>('');
  const [filtroPrioridad, setFiltroPrioridad] = useState<'' | Prioridad>('');
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const [editando, setEditando] = useState<Tarea | null>(null);
  const [titulo, setTitulo] = useState('');
  const [prioridad, setPrioridad] = useState<Prioridad>('media');
  const [fechaLimite, setFechaLimite] = useState('');
  const [errores, setErrores] = useState<Partial<Record<'titulo' | 'fecha', string>>>({});

  const cargar = useCallback(async () => {
    try {
      const [lista, res] = await Promise.all([
        tasksApi.list({ estado: filtroEstado || undefined, prioridad: filtroPrioridad || undefined }),
        tasksApi.summary(),
      ]);
      setTareas(lista);
      setResumen(res);
      setError(null);
    } catch (e) {
      setError(errorDe(e));
    }
  }, [filtroEstado, filtroPrioridad]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  const limpiarFormulario = () => {
    setEditando(null);
    setTitulo('');
    setPrioridad('media');
    setFechaLimite('');
    setErrores({});
  };

  const validar = (): boolean => {
    const nuevos: typeof errores = {};
    if (!titulo.trim()) nuevos.titulo = 'Escribe el título de la tarea.';
    else if (titulo.trim().length > TITULO_MAX) nuevos.titulo = `Máximo ${TITULO_MAX} caracteres.`;
    if (fechaLimite && !/^\d{4}-\d{2}-\d{2}$/.test(fechaLimite)) nuevos.fecha = 'Usa el formato AAAA-MM-DD.';
    setErrores(nuevos);
    return Object.keys(nuevos).length === 0;
  };

  const guardar = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!validar()) return;
    setError(null);
    setOk(null);
    const cuerpo = {
      titulo: titulo.trim(),
      prioridad,
      fecha_limite: fechaLimite || null,
    };
    try {
      if (editando) {
        await tasksApi.update(editando.id, cuerpo);
        setOk(`Tarea «${cuerpo.titulo}» actualizada.`);
      } else {
        await tasksApi.create({ ...cuerpo, estado: 'pendiente' });
        setOk(`Tarea «${cuerpo.titulo}» creada.`);
      }
      limpiarFormulario();
      await cargar();
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const editar = (t: Tarea) => {
    setEditando(t);
    setTitulo(t.titulo);
    setPrioridad(t.prioridad);
    setFechaLimite(t.fecha_limite ?? '');
    setErrores({});
    setOk(null);
    document.getElementById('tarea-titulo')?.focus();
  };

  const cambiarEstado = async (t: Tarea) => {
    const nuevo: EstadoTarea = t.estado === 'pendiente' ? 'completada' : 'pendiente';
    setError(null);
    setOk(null);
    try {
      await tasksApi.update(t.id, { estado: nuevo });
      setOk(nuevo === 'completada' ? `«${t.titulo}» completada.` : `«${t.titulo}» vuelve a pendiente.`);
      await cargar();
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const eliminar = async (t: Tarea) => {
    setError(null);
    setOk(null);
    try {
      await tasksApi.remove(t.id);
      if (editando?.id === t.id) limpiarFormulario();
      setOk(`Tarea «${t.titulo}» eliminada.`);
      await cargar();
    } catch (e) {
      setError(errorDe(e));
    }
  };

  if (tareas === null && !error) return <Cargando texto="Cargando tareas…" />;

  return (
    <section aria-labelledby="titulo-tareas" className="module">
      <header className="module__header">
        <div>
          <p className="eyebrow">Módulo</p>
          <h1 id="titulo-tareas">Tareas</h1>
          <p className="muted">Prioridad alta, media o baja, con fecha límite opcional. El orden lo calcula el servidor.</p>
        </div>
      </header>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {ok && <Aviso tipo="ok">{ok}</Aviso>}

      <div className="kpis">
        <Kpi etiqueta="Total" valor={resumen?.total ?? 0} tono="sky" />
        <Kpi etiqueta="Pendientes" valor={resumen?.pendientes ?? 0} tono="orange" />
        <Kpi etiqueta="Completadas" valor={resumen?.completadas ?? 0} tono="green" />
        <Kpi etiqueta="Vencidas" valor={resumen?.vencidas.length ?? 0} tono="red" detalle="Pendientes con fecha pasada" />
      </div>

      <div className="panel">
        <div className="panel__cabecera">
          <h2>Progreso</h2>
          <strong>{formatPorcentaje(resumen?.porcentaje ?? '0')}</strong>
        </div>
        <Progreso valor={Number(resumen?.porcentaje ?? 0)} etiqueta="Porcentaje de tareas completadas" />
      </div>

      <div className="split">
        <div className="panel">
          <h2>{editando ? 'Editar tarea' : 'Nueva tarea'}</h2>
          <form onSubmit={guardar} className="form-grid" noValidate>
            <div className="field">
              <label htmlFor="tarea-titulo">Título</label>
              <input
                id="tarea-titulo"
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                maxLength={TITULO_MAX}
                placeholder="Entregar taller de cálculo"
                aria-invalid={!!errores.titulo}
                aria-describedby={errores.titulo ? 'error-tarea-titulo' : undefined}
              />
              {errores.titulo && <p id="error-tarea-titulo" className="field-error">{errores.titulo}</p>}
            </div>
            <div className="field">
              <label htmlFor="tarea-prioridad">Prioridad</label>
              <select id="tarea-prioridad" value={prioridad} onChange={(e) => setPrioridad(e.target.value as Prioridad)}>
                <option value="alta">Alta</option>
                <option value="media">Media</option>
                <option value="baja">Baja</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="tarea-fecha">Fecha límite (opcional)</label>
              <input
                id="tarea-fecha"
                type="date"
                value={fechaLimite}
                onChange={(e) => setFechaLimite(e.target.value)}
                aria-invalid={!!errores.fecha}
                aria-describedby={errores.fecha ? 'error-tarea-fecha' : undefined}
              />
              {errores.fecha && <p id="error-tarea-fecha" className="field-error">{errores.fecha}</p>}
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn--primary">{editando ? 'Guardar cambios' : 'Crear tarea'}</button>
              {editando && (
                <button type="button" className="btn" onClick={limpiarFormulario}>Cancelar edición</button>
              )}
            </div>
          </form>

          <h2 className="mt">Próximas a vencer (7 días)</h2>
          {resumen && resumen.proximas.length === 0 && resumen.vencidas.length === 0 && (
            <p className="muted">No tienes tareas pendientes con fecha cercana.</p>
          )}
          <ul className="list" aria-label="Tareas próximas a vencer">
            {[...(resumen?.vencidas ?? []), ...(resumen?.proximas ?? [])].map((t) => (
              <li key={`aviso-${t.id}`} className="list__item list__item--static">
                <span className="list__titulo">{t.titulo}</span>
                <span className="list__meta">
                  <Badge tono={t.vencida ? 'bad' : 'warn'}>{t.vencida ? 'Vencida' : 'Próxima'}</Badge> {textoVencimiento(t)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel">
          <div className="filtros">
            <div className="field field--compact">
              <label htmlFor="filtro-estado">Estado</label>
              <select id="filtro-estado" value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value as '' | EstadoTarea)}>
                <option value="">Todas</option>
                <option value="pendiente">Pendientes</option>
                <option value="completada">Completadas</option>
              </select>
            </div>
            <div className="field field--compact">
              <label htmlFor="filtro-prioridad">Prioridad</label>
              <select id="filtro-prioridad" value={filtroPrioridad} onChange={(e) => setFiltroPrioridad(e.target.value as '' | Prioridad)}>
                <option value="">Todas</option>
                {PRIORIDADES.map((p) => (
                  <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>

          {tareas && tareas.length === 0 ? (
            <EstadoVacio
              titulo={filtroEstado || filtroPrioridad ? 'Ninguna tarea coincide con el filtro' : 'Sin tareas'}
              texto={filtroEstado || filtroPrioridad ? 'Cambia los filtros para ver otras tareas.' : 'Crea tu primera tarea con el formulario.'}
            />
          ) : (
            <ul className="list list--tareas" aria-label="Lista de tareas">
              {(tareas ?? []).map((t) => (
                <li key={t.id} className={`list__item list__item--static tarea prioridad prioridad--${t.prioridad} ${t.estado === 'completada' ? 'is-done' : ''}`}>
                  <label className="tarea__check">
                    <input
                      type="checkbox"
                      checked={t.estado === 'completada'}
                      onChange={() => void cambiarEstado(t)}
                      aria-label={`Marcar «${t.titulo}» como ${t.estado === 'completada' ? 'pendiente' : 'completada'}`}
                    />
                  </label>
                  <div className="tarea__cuerpo">
                    <span className="list__titulo">
                      {t.titulo}
                      {t.origen === 'demo' && <Badge tono="demo">Demo</Badge>}
                    </span>
                    <span className="list__meta">
                      <Badge tono={toneDePrioridad(t.prioridad)}>{t.prioridad[0].toUpperCase() + t.prioridad.slice(1)}</Badge>{' '}
                      <span className={t.vencida ? 'texto-alerta' : ''}>{textoVencimiento(t)}</span>
                    </span>
                  </div>
                  <div className="tarea__acciones">
                    <button type="button" className="btn btn--ghost btn--small" onClick={() => editar(t)} aria-label={`Editar ${t.titulo}`}>
                      Editar
                    </button>
                    <BotonConfirmar
                      etiqueta={`Eliminar ${t.titulo}`}
                      confirmacion={`Se eliminará la tarea «${t.titulo}».`}
                      onConfirmar={() => void eliminar(t)}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
