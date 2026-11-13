import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { academicApi, type NotaNecesaria, type ResumenAcademico, type Subject, type SubjectDetail } from '../api/academic';
import { ApiError } from '../api/http';
import { BarrasHorizontales } from '../components/charts';
import { Aviso, Badge, BotonConfirmar, Cargando, EstadoVacio, Kpi } from '../components/ui';
import { formatNota } from '../lib/format';

const NOMBRE_MAX = 120;
const DESCRIPCION_MAX = 200;

function errorDe(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación. Intenta de nuevo.';
}

/** Valida un número 0–5 con hasta dos decimales. Devuelve el número o el mensaje de error. */
function validarEntre0y5(texto: string, etiqueta: 'nota' | 'objetivo'): number | string {
  const limpio = texto.trim().replace(',', '.');
  const Etiqueta = etiqueta === 'nota' ? 'La nota' : 'El objetivo';
  if (limpio === '') return etiqueta === 'nota' ? 'Ingresa la nota.' : 'Ingresa el objetivo.';
  const numero = Number(limpio);
  if (!Number.isFinite(numero)) return `${Etiqueta} debe ser un número.`;
  if (numero < 0 || numero > 5) return `${Etiqueta} debe estar entre 0 y 5.`;
  if (/\.\d{3,}/.test(limpio)) return 'Usa como máximo dos decimales.'; // sobre el texto: evita errores binarios (4,1 × 100)
  return numero;
}

export default function AcademicPage() {
  const [asignaturas, setAsignaturas] = useState<Subject[] | null>(null);
  const [resumen, setResumen] = useState<ResumenAcademico | null>(null);
  const [seleccionada, setSeleccionada] = useState<SubjectDetail | null>(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  // Id de la asignatura abierta. Es una referencia (no un valor de render) para que las
  // recargas posteriores a una acción siempre apunten a la asignatura ACTUAL, no a una capturada antes.
  const idSeleccionada = useRef<string | null>(null);

  const [nuevoNombre, setNuevoNombre] = useState('');
  const [errorNombre, setErrorNombre] = useState<string | null>(null);
  const [descripcion, setDescripcion] = useState('');
  const [nota, setNota] = useState('');
  const [errorNota, setErrorNota] = useState<string | null>(null);
  const [errorDescripcion, setErrorDescripcion] = useState<string | null>(null);
  const [renombrar, setRenombrar] = useState('');
  const [objetivo, setObjetivo] = useState('3.0');
  const [necesaria, setNecesaria] = useState<NotaNecesaria | null>(null);
  const [errorObjetivo, setErrorObjetivo] = useState<string | null>(null);

  const cargarLista = useCallback(async () => {
    try {
      const [lista, res] = await Promise.all([academicApi.listSubjects(), academicApi.resumen()]);
      setAsignaturas(lista);
      setResumen(res);
    } catch (e) {
      setError(errorDe(e));
    }
  }, []);

  const cargarDetalle = useCallback(async (id: string) => {
    setCargandoDetalle(true);
    try {
      const detalle = await academicApi.getSubject(id);
      idSeleccionada.current = id;
      setSeleccionada(detalle);
      setRenombrar(detalle.nombre);
      setNecesaria(null);
    } catch (e) {
      idSeleccionada.current = null;
      setSeleccionada(null);
      setError(errorDe(e));
    } finally {
      setCargandoDetalle(false);
    }
  }, []);

  useEffect(() => {
    void cargarLista();
  }, [cargarLista]);

  const refrescar = async () => {
    await cargarLista();
    const id = idSeleccionada.current;
    if (id) await cargarDetalle(id);
  };

  const ejecutar = async (accion: () => Promise<unknown>, mensajeOk: string) => {
    setError(null);
    setOk(null);
    try {
      await accion();
      setOk(mensajeOk);
      await refrescar();
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const crearAsignatura = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    const nombre = nuevoNombre.trim();
    if (!nombre) return setErrorNombre('Escribe el nombre de la asignatura.');
    if (nombre.length > NOMBRE_MAX) return setErrorNombre(`Máximo ${NOMBRE_MAX} caracteres.`);
    setErrorNombre(null);
    void ejecutar(async () => {
      const creada = await academicApi.createSubject(nombre);
      setNuevoNombre('');
      await cargarDetalle(creada.id);
    }, `Asignatura «${nombre}» creada.`);
  };

  const agregarNota = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!seleccionada) return;
    const texto = descripcion.trim();
    const valor = validarEntre0y5(nota, 'nota');
    setErrorDescripcion(texto ? null : 'Describe la evaluación (p. ej. «Parcial 1»).');
    setErrorNota(typeof valor === 'string' ? valor : null);
    if (!texto || typeof valor === 'string') return;
    void ejecutar(async () => {
      await academicApi.addGrade(seleccionada.id, texto, valor);
      setDescripcion('');
      setNota('');
    }, `Nota registrada: ${texto} (${formatNota(valor)}).`);
  };

  const eliminarNota = (id: string, descripcionNota: string) =>
    void ejecutar(() => academicApi.deleteGrade(id), `Nota «${descripcionNota}» eliminada.`);

  const eliminarAsignatura = async () => {
    if (!seleccionada) return;
    const { id, nombre } = seleccionada;
    setError(null);
    setOk(null);
    try {
      await academicApi.deleteSubject(id);
      idSeleccionada.current = null;
      setSeleccionada(null);
      setOk(`Asignatura «${nombre}» eliminada con sus notas.`);
      await cargarLista();
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const guardarNombre = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!seleccionada) return;
    const nombre = renombrar.trim();
    if (!nombre || nombre === seleccionada.nombre) return;
    void ejecutar(() => academicApi.renameSubject(seleccionada.id, nombre), 'Nombre actualizado.');
  };

  const calcularObjetivo = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!seleccionada) return;
    const valor = validarEntre0y5(objetivo, 'objetivo');
    if (typeof valor === 'string') return setErrorObjetivo(valor);
    setErrorObjetivo(null);
    try {
      setNecesaria(await academicApi.notaNecesaria(seleccionada.id, valor));
    } catch (e) {
      setErrorObjetivo(errorDe(e));
    }
  };

  if (asignaturas === null && !error) return <Cargando texto="Cargando asignaturas…" />;

  const grafica = (asignaturas ?? [])
    .filter((a) => a.promedio !== null)
    .map((a) => ({ etiqueta: a.nombre, valor: Number(a.promedio), texto: formatNota(a.promedio) }));

  return (
    <section aria-labelledby="titulo-academico" className="module">
      <header className="module__header">
        <div>
          <p className="eyebrow">Módulo</p>
          <h1 id="titulo-academico">Académico</h1>
          <p className="muted">
            Asignaturas, notas y promedios. Aprobación desde 3,00 sobre 5. Todas las notas de una asignatura pesan igual:
            las ponderaciones aún no están implementadas.
          </p>
        </div>
      </header>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {ok && <Aviso tipo="ok">{ok}</Aviso>}

      <div className="kpis">
        <Kpi etiqueta="Asignaturas" valor={resumen?.total_asignaturas ?? 0} tono="sky" />
        <Kpi etiqueta="Aprobadas" valor={resumen?.aprobadas ?? 0} tono="green" detalle={`de ${resumen?.con_notas ?? 0} con notas`} />
        <Kpi etiqueta="Reprobadas" valor={resumen?.reprobadas ?? 0} tono="red" />
        <Kpi
          etiqueta="Promedio general"
          valor={formatNota(resumen?.promedio_general ?? null)}
          tono="violet"
          detalle="Cada asignatura pesa igual"
        />
      </div>

      <div className="split">
        <aside className="panel" aria-labelledby="lista-asignaturas">
          <h2 id="lista-asignaturas">Asignaturas</h2>
          <form onSubmit={crearAsignatura} className="form-inline" noValidate>
            <label htmlFor="nueva-asignatura" className="visually-hidden">Nombre de la nueva asignatura</label>
            <input
              id="nueva-asignatura"
              value={nuevoNombre}
              onChange={(e) => setNuevoNombre(e.target.value)}
              placeholder="Nueva asignatura"
              maxLength={NOMBRE_MAX + 20}
              aria-invalid={errorNombre !== null}
              aria-describedby={errorNombre ? 'error-nueva-asignatura' : undefined}
            />
            <button type="submit" className="btn btn--primary">Agregar</button>
          </form>
          {errorNombre && <p id="error-nueva-asignatura" className="field-error">{errorNombre}</p>}

          {asignaturas && asignaturas.length === 0 ? (
            <EstadoVacio titulo="Sin asignaturas" texto="Agrega tu primera asignatura para registrar notas." />
          ) : (
            <ul className="list" aria-label="Lista de asignaturas">
              {(asignaturas ?? []).map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    className={`list__item ${seleccionada?.id === a.id ? 'is-active' : ''}`}
                    aria-current={seleccionada?.id === a.id ? 'true' : undefined}
                    onClick={() => void cargarDetalle(a.id)}
                  >
                    <span className="list__titulo">
                      {a.nombre}
                      {a.origen === 'demo' && <Badge tono="demo">Demo</Badge>}
                    </span>
                    <span className="list__meta">
                      {a.total_notas} {a.total_notas === 1 ? 'nota' : 'notas'} · promedio {formatNota(a.promedio)}
                      {a.aprobado !== null && (
                        <> · <Badge tono={a.aprobado ? 'ok' : 'bad'}>{a.aprobado ? 'Aprobada' : 'Reprobada'}</Badge></>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {grafica.length > 0 && <BarrasHorizontales titulo="Promedio por asignatura (0 a 5)" items={grafica} maximo={5} />}
        </aside>

        <div className="panel" aria-live="polite">
          {cargandoDetalle && <Cargando texto="Cargando asignatura…" />}
          {!cargandoDetalle && !seleccionada && (
            <EstadoVacio titulo="Selecciona una asignatura" texto="Verás sus notas, su promedio y la nota que necesitas para tu objetivo." />
          )}

          {!cargandoDetalle && seleccionada && (
            <>
              <div className="panel__cabecera">
                <div>
                  <h2>{seleccionada.nombre}</h2>
                  <p className="muted">
                    Promedio <strong>{formatNota(seleccionada.promedio)}</strong>
                    {seleccionada.aprobado !== null && (
                      <> · <Badge tono={seleccionada.aprobado ? 'ok' : 'bad'}>{seleccionada.aprobado ? 'Aprobada' : 'Reprobada'}</Badge></>
                    )}
                  </p>
                </div>
                <BotonConfirmar
                  etiqueta="Eliminar asignatura"
                  confirmacion={`Se eliminarán «${seleccionada.nombre}» y sus ${seleccionada.total_notas} notas. Esta acción no se puede deshacer.`}
                  onConfirmar={eliminarAsignatura}
                />
              </div>

              <form onSubmit={guardarNombre} className="form-inline">
                <label htmlFor="renombrar" className="visually-hidden">Nombre de la asignatura</label>
                <input id="renombrar" value={renombrar} onChange={(e) => setRenombrar(e.target.value)} maxLength={NOMBRE_MAX} />
                <button type="submit" className="btn">Renombrar</button>
              </form>

              <h3>Notas</h3>
              {seleccionada.notas.length === 0 ? (
                <EstadoVacio titulo="Sin notas" texto="Registra la primera nota de esta asignatura." />
              ) : (
                <ul className="list list--notas" aria-label="Notas registradas">
                  {seleccionada.notas.map((n) => (
                    <li key={n.id} className="list__item list__item--static">
                      <span className="list__titulo">
                        {n.descripcion}
                        {n.origen === 'demo' && <Badge tono="demo">Demo</Badge>}
                      </span>
                      <span className="nota-valor">
                        <strong>{formatNota(n.nota)}</strong>
                        <Badge tono={n.aprobado ? 'ok' : 'bad'}>{n.aprobado ? 'Aprobada' : 'Reprobada'}</Badge>
                        <BotonConfirmar
                          etiqueta={`Eliminar nota ${n.descripcion}`}
                          confirmacion={`Se eliminará la nota «${n.descripcion}» (${formatNota(n.nota)}).`}
                          onConfirmar={() => eliminarNota(n.id, n.descripcion)}
                        />
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {seleccionada.notas.length > 0 && (
                <BarrasHorizontales
                  titulo="Notas por evaluación (0 a 5)"
                  maximo={5}
                  items={seleccionada.notas.map((n) => ({ etiqueta: n.descripcion, valor: Number(n.nota), texto: formatNota(n.nota) }))}
                />
              )}

              <form onSubmit={agregarNota} className="form-grid" noValidate>
                <div className="field">
                  <label htmlFor="nota-descripcion">Evaluación</label>
                  <input
                    id="nota-descripcion"
                    value={descripcion}
                    onChange={(e) => setDescripcion(e.target.value)}
                    maxLength={DESCRIPCION_MAX}
                    placeholder="Parcial 1"
                    aria-invalid={errorDescripcion !== null}
                    aria-describedby={errorDescripcion ? 'error-nota-descripcion' : undefined}
                  />
                  {errorDescripcion && <p id="error-nota-descripcion" className="field-error">{errorDescripcion}</p>}
                </div>
                <div className="field">
                  <label htmlFor="nota-valor">Nota (0 a 5)</label>
                  <input
                    id="nota-valor"
                    inputMode="decimal"
                    value={nota}
                    onChange={(e) => setNota(e.target.value)}
                    placeholder="4,50"
                    aria-invalid={errorNota !== null}
                    aria-describedby={errorNota ? 'error-nota-valor' : undefined}
                  />
                  {errorNota && <p id="error-nota-valor" className="field-error">{errorNota}</p>}
                </div>
                <button type="submit" className="btn btn--primary">Registrar nota</button>
              </form>

              <h3>Nota necesaria para tu objetivo</h3>
              <form onSubmit={calcularObjetivo} className="form-inline" noValidate>
                <label htmlFor="objetivo">Promedio objetivo (0 a 5)</label>
                <input
                  id="objetivo"
                  inputMode="decimal"
                  value={objetivo}
                  onChange={(e) => setObjetivo(e.target.value)}
                  aria-invalid={errorObjetivo !== null}
                  aria-describedby={errorObjetivo ? 'error-objetivo' : undefined}
                />
                <button type="submit" className="btn">Calcular</button>
              </form>
              {errorObjetivo && <p id="error-objetivo" className="field-error">{errorObjetivo}</p>}
              {necesaria && (
                <Aviso tipo={necesaria.posible ? 'ok' : 'error'}>
                  {necesaria.mensaje}
                </Aviso>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
