import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { financeApi, type Gasto, type PresupuestoDetalle, type TipoGasto } from '../api/finance';
import { ApiError } from '../api/http';
import { BarrasHorizontales, Dona } from '../components/charts';
import { Aviso, Badge, BotonConfirmar, Cargando, EstadoVacio, Kpi, Progreso } from '../components/ui';
import { Icono } from '../components/icons';
import { formatCop, formatFecha, formatPorcentaje, hoyIso, mesActual } from '../lib/format';

const CONCEPTO_MAX = 200;
const CATEGORIA_MAX = 60;

/** Importe de la API formateado para el campo de entrada (es-CO: 2.500.000). */
const entradaImporte = (valor: string): string =>
  new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(Number(valor));

function errorDe(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación. Intenta de nuevo.';
}

/** Número no negativo con hasta dos decimales. Devuelve el número o el mensaje de error. */
function validarImporte(texto: string, etiqueta: string): number | string {
  const bruto = texto.trim();
  // Formato colombiano: el punto separa miles (2.000.000) y la coma decimales (1.500,50).
  const limpio = /^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(bruto)
    ? bruto.replace(/\./g, '').replace(',', '.')
    : bruto.replace(',', '.');
  if (limpio === '') return `Ingresa ${etiqueta}.`;
  const numero = Number(limpio);
  if (!Number.isFinite(numero)) return `${etiqueta[0].toUpperCase()}${etiqueta.slice(1)} debe ser un número.`;
  if (numero < 0) return `${etiqueta[0].toUpperCase()}${etiqueta.slice(1)} no puede ser negativo.`;
  if (/\.\d{3,}/.test(limpio)) return 'Usa como máximo dos decimales.'; // sobre el texto: evita errores binarios (4,1 × 100)
  return numero;
}

const primerDia = (anio: number, mes: number) => `${anio}-${String(mes).padStart(2, '0')}-01`;
const ultimoDia = (anio: number, mes: number) => {
  const fin = new Date(anio, mes, 0).getDate();
  return `${anio}-${String(mes).padStart(2, '0')}-${String(fin).padStart(2, '0')}`;
};

function periodoTexto(anio: number, mes: number): string {
  return new Date(anio, mes - 1, 1).toLocaleDateString('es-CO', { month: 'long', year: 'numeric' });
}

export default function FinancePage() {
  const actual = mesActual();
  const [periodo, setPeriodo] = useState(`${actual.anio}-${String(actual.mes).padStart(2, '0')}`);
  const [anio, mes] = useMemo(() => {
    const [a, m] = periodo.split('-').map(Number);
    return [a, m];
  }, [periodo]);

  const [detalle, setDetalle] = useState<PresupuestoDetalle | null>(null);
  const [sinPresupuesto, setSinPresupuesto] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const [ingreso, setIngreso] = useState('');
  const [meta, setMeta] = useState('');
  const [errorPresupuesto, setErrorPresupuesto] = useState<string | null>(null);

  const [concepto, setConcepto] = useState('');
  const [categoria, setCategoria] = useState('');
  const [monto, setMonto] = useState('');
  const [tipo, setTipo] = useState<TipoGasto>('variable');
  const [fecha, setFecha] = useState(() => (periodo === `${actual.anio}-${String(actual.mes).padStart(2, '0')}` ? hoyIso() : primerDia(anio, mes)));
  const [erroresGasto, setErroresGasto] = useState<Partial<Record<'concepto' | 'categoria' | 'monto' | 'fecha', string>>>({});

  const cargar = useCallback(async (a: number, m: number) => {
    setCargando(true);
    setError(null);
    try {
      const d = await financeApi.getBudget(a, m);
      setDetalle(d);
      setSinPresupuesto(false);
      setIngreso(entradaImporte(d.ingreso));
      setMeta(entradaImporte(d.meta_ahorro));
    } catch (e) {
      setDetalle(null);
      if (e instanceof ApiError && e.status === 404) {
        setSinPresupuesto(true);
        setIngreso('');
        setMeta('');
      } else {
        setError(errorDe(e));
      }
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar(anio, mes);
    const esActual = anio === actual.anio && mes === actual.mes;
    setFecha(esActual ? hoyIso() : primerDia(anio, mes));
    setOk(null);
  }, [anio, mes, cargar, actual.anio, actual.mes]);

  const guardarPresupuesto = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    const valorIngreso = validarImporte(ingreso, 'el ingreso mensual');
    const valorMeta = meta.trim() === '' ? 0 : validarImporte(meta, 'la meta de ahorro');
    if (typeof valorIngreso === 'string') return setErrorPresupuesto(valorIngreso);
    if (typeof valorMeta === 'string') return setErrorPresupuesto(valorMeta);
    setErrorPresupuesto(null);
    setError(null);
    setOk(null);
    try {
      await financeApi.defineBudget(anio, mes, valorIngreso, valorMeta);
      setOk('Presupuesto del mes guardado.');
      await cargar(anio, mes);
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const validarGasto = (): Record<string, string> => {
    const errores: Record<string, string> = {};
    if (!concepto.trim()) errores.concepto = 'Describe el gasto.';
    if (!categoria.trim()) errores.categoria = 'Indica la categoría (p. ej. Alimentación).';
    if (categoria.trim().length > CATEGORIA_MAX) errores.categoria = `Máximo ${CATEGORIA_MAX} caracteres.`;
    const valorMonto = validarImporte(monto, 'el monto');
    if (typeof valorMonto === 'string') errores.monto = valorMonto;
    if (!fecha) errores.fecha = 'Indica la fecha del gasto.';
    else if (fecha < primerDia(anio, mes) || fecha > ultimoDia(anio, mes)) errores.fecha = 'La fecha debe estar dentro del mes seleccionado.';
    return errores;
  };

  const registrarGasto = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    const errores = validarGasto();
    setErroresGasto(errores);
    if (Object.keys(errores).length) return;
    const valorMonto = validarImporte(monto, 'el monto');
    if (typeof valorMonto === 'string') return;
    setError(null);
    setOk(null);
    try {
      await financeApi.addExpense(anio, mes, {
        descripcion: concepto.trim(),
        categoria: categoria.trim(),
        monto: valorMonto,
        tipo,
        fecha,
      });
      setConcepto('');
      setMonto('');
      setOk(`Gasto registrado: ${concepto.trim()} (${formatCop(valorMonto)}).`);
      await cargar(anio, mes);
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const eliminarGasto = async (id: string, nombre: string) => {
    setError(null);
    setOk(null);
    try {
      await financeApi.deleteExpense(id);
      setOk(`Gasto «${nombre}» eliminado.`);
      await cargar(anio, mes);
    } catch (e) {
      setError(errorDe(e));
    }
  };

  // ----- edición de gastos (endpoint PATCH existente) -----
  const [editando, setEditando] = useState<Gasto | null>(null);
  const [ed, setEd] = useState({ descripcion: '', categoria: '', monto: '', tipo: 'variable' as TipoGasto, fecha: '' });
  const [errEd, setErrEd] = useState<Partial<Record<'descripcion' | 'categoria' | 'monto' | 'fecha', string>>>({});

  const empezarEdicion = (g: Gasto) => {
    setEditando(g);
    setEd({ descripcion: g.descripcion, categoria: g.categoria, monto: String(Number(g.monto)), tipo: g.tipo, fecha: g.fecha });
    setErrEd({});
    setOk(null);
    document.getElementById('edicion-gasto')?.scrollIntoView({ block: 'nearest' });
  };

  const guardarEdicion = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    if (!editando) return;
    const errores: typeof errEd = {};
    if (!ed.descripcion.trim()) errores.descripcion = 'Describe el gasto.';
    if (!ed.categoria.trim()) errores.categoria = 'Indica la categoría.';
    const valorMonto = validarImporte(ed.monto, 'el monto');
    if (typeof valorMonto === 'string') errores.monto = valorMonto;
    if (!ed.fecha || ed.fecha < primerDia(anio, mes) || ed.fecha > ultimoDia(anio, mes)) {
      errores.fecha = 'La fecha debe estar dentro del mes seleccionado.';
    }
    setErrEd(errores);
    if (Object.keys(errores).length || typeof valorMonto === 'string') return;
    setError(null);
    try {
      await financeApi.updateExpense(editando.id, {
        descripcion: ed.descripcion.trim(),
        categoria: ed.categoria.trim(),
        monto: valorMonto,
        tipo: ed.tipo,
        fecha: ed.fecha,
      });
      setOk(`Gasto «${ed.descripcion.trim()}» actualizado.`);
      setEditando(null);
      await cargar(anio, mes);
    } catch (e) {
      setError(errorDe(e));
    }
  };

  const categoriasConocidas = useMemo(
    () => Array.from(new Set((detalle?.gastos ?? []).map((g) => g.categoria))).sort(),
    [detalle],
  );

  const porcentajeUso = detalle && Number(detalle.ingreso) > 0
    ? Math.min(100, (Number(detalle.gastos_total) / Number(detalle.ingreso)) * 100)
    : 0;

  return (
    <section aria-labelledby="titulo-finanzas" className="module">
      <header className="module__header">
        <div>
          <p className="eyebrow">Módulo</p>
          <h1 id="titulo-finanzas">Finanzas personales</h1>
          <p className="muted">Presupuesto mensual en pesos colombianos (COP).</p>
        </div>
        <div className="field field--compact">
          <label htmlFor="periodo">Mes</label>
          <input id="periodo" type="month" value={periodo} onChange={(e) => e.target.value && setPeriodo(e.target.value)} />
        </div>
      </header>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {ok && <Aviso tipo="ok">{ok}</Aviso>}

      {cargando && <Cargando texto="Cargando presupuesto…" />}

      {!cargando && sinPresupuesto && (
        <EstadoVacio titulo="Este mes aún no tiene presupuesto" texto="Define el ingreso mensual y, si quieres, tu meta de ahorro para empezar a registrar gastos." />
      )}

      {!cargando && (
        <form onSubmit={guardarPresupuesto} className="form-inline panel" noValidate aria-labelledby="titulo-presupuesto">
          <h2 id="titulo-presupuesto" className="visually-hidden">Presupuesto del mes</h2>
          <div className="field">
            <label htmlFor="ingreso">Ingreso mensual (COP)</label>
            <input
              id="ingreso"
              inputMode="decimal"
              value={ingreso}
              onChange={(e) => setIngreso(e.target.value)}
              placeholder="2.000.000"
              aria-invalid={errorPresupuesto !== null}
              aria-describedby={errorPresupuesto ? 'error-presupuesto' : undefined}
            />
          </div>
          <div className="field">
            <label htmlFor="meta">Meta de ahorro (COP)</label>
            <input id="meta" inputMode="decimal" value={meta} onChange={(e) => setMeta(e.target.value)} placeholder="300.000" />
          </div>
          <button type="submit" className="btn btn--primary">Guardar presupuesto</button>
          {errorPresupuesto && <p id="error-presupuesto" className="field-error">{errorPresupuesto}</p>}
        </form>
      )}

      {!cargando && detalle && (
        <>
          <div className="kpis">
            <Kpi etiqueta="Ingreso del mes" valor={formatCop(detalle.ingreso)} tono="sky" />
            <Kpi
              etiqueta="Gasto acumulado"
              valor={formatCop(detalle.gastos_total)}
              tono="orange"
              detalle={`${formatCop(detalle.gastos_fijos)} fijos · ${formatCop(detalle.gastos_variables)} variables`}
            />
            <Kpi
              etiqueta="Saldo"
              valor={formatCop(detalle.saldo)}
              tono={Number(detalle.saldo) >= 0 ? 'green' : 'red'}
              detalle={Number(detalle.saldo) >= 0 ? 'Lo que queda del ingreso' : 'Gastaste más de tu ingreso'}
            />
            <Kpi
              etiqueta="Ahorro logrado"
              valor={formatCop(detalle.ahorro_logrado)}
              tono="violet"
              detalle={`Disponible para gastar: ${formatCop(detalle.disponible_para_gastar)}`}
            />
          </div>

          <div className="panel">
            <div className="panel__cabecera">
              <h2>Uso del ingreso</h2>
              {Number(detalle.meta_ahorro) > 0 && (
                <Badge tono={detalle.meta_cumplida ? 'ok' : 'warn'}>
                  {detalle.meta_cumplida ? 'Meta de ahorro cumplida' : 'Meta de ahorro no cumplida'}
                </Badge>
              )}
            </div>
            <p className="muted">Gastado: {formatPorcentaje(porcentajeUso)} del ingreso · Meta de ahorro: {formatCop(detalle.meta_ahorro)}</p>
            <Progreso valor={porcentajeUso} etiqueta="Porcentaje del ingreso gastado" />
          </div>

          <div className="split">
            <div className="panel">
              <h2>Registrar gasto</h2>
              <form onSubmit={registrarGasto} className="form-grid" noValidate>
                <div className="field">
                  <label htmlFor="gasto-concepto">Descripción</label>
                  <input
                    id="gasto-concepto"
                    value={concepto}
                    onChange={(e) => setConcepto(e.target.value)}
                    maxLength={CONCEPTO_MAX}
                    placeholder="Mercado semanal"
                    aria-invalid={!!erroresGasto.concepto}
                    aria-describedby={erroresGasto.concepto ? 'error-gasto-concepto' : undefined}
                  />
                  {erroresGasto.concepto && <p id="error-gasto-concepto" className="field-error">{erroresGasto.concepto}</p>}
                </div>
                <div className="field">
                  <label htmlFor="gasto-categoria">Categoría</label>
                  <input
                    id="gasto-categoria"
                    list="categorias-existentes"
                    value={categoria}
                    onChange={(e) => setCategoria(e.target.value)}
                    maxLength={CATEGORIA_MAX}
                    placeholder="Alimentación"
                    aria-invalid={!!erroresGasto.categoria}
                    aria-describedby={erroresGasto.categoria ? 'error-gasto-categoria' : undefined}
                  />
                  <datalist id="categorias-existentes">
                    {categoriasConocidas.map((c) => <option key={c} value={c} />)}
                  </datalist>
                  {erroresGasto.categoria && <p id="error-gasto-categoria" className="field-error">{erroresGasto.categoria}</p>}
                </div>
                <div className="field">
                  <label htmlFor="gasto-monto">Monto (COP)</label>
                  <input
                    id="gasto-monto"
                    inputMode="decimal"
                    value={monto}
                    onChange={(e) => setMonto(e.target.value)}
                    placeholder="120.000"
                    aria-invalid={!!erroresGasto.monto}
                    aria-describedby={erroresGasto.monto ? 'error-gasto-monto' : undefined}
                  />
                  {erroresGasto.monto && <p id="error-gasto-monto" className="field-error">{erroresGasto.monto}</p>}
                </div>
                <div className="field">
                  <label htmlFor="gasto-tipo">Tipo</label>
                  <select id="gasto-tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoGasto)}>
                    <option value="fijo">Fijo (se repite cada mes)</option>
                    <option value="variable">Variable</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="gasto-fecha">Fecha</label>
                  <input
                    id="gasto-fecha"
                    type="date"
                    min={primerDia(anio, mes)}
                    max={ultimoDia(anio, mes)}
                    value={fecha}
                    onChange={(e) => setFecha(e.target.value)}
                    aria-invalid={!!erroresGasto.fecha}
                    aria-describedby={erroresGasto.fecha ? 'error-gasto-fecha' : undefined}
                  />
                  {erroresGasto.fecha && <p id="error-gasto-fecha" className="field-error">{erroresGasto.fecha}</p>}
                </div>
                <button type="submit" className="btn btn--primary">Registrar gasto</button>
              </form>
            </div>

            <div className="panel">
              {detalle.categorias.length === 0 ? (
                <EstadoVacio titulo="Sin distribución aún" texto="Cuando registres gastos verás cuánto va a cada categoría." />
              ) : (
                <>
                  <Dona
                    titulo="Distribución por categoría"
                    items={detalle.categorias.map((c) => ({
                      etiqueta: c.categoria,
                      porcentaje: Number(c.porcentaje),
                      texto: `${formatPorcentaje(c.porcentaje)} · ${formatCop(c.total)}`,
                    }))}
                  />
                  <BarrasHorizontales
                    titulo="Gasto por categoría (COP)"
                    items={detalle.categorias.map((c) => ({ etiqueta: c.categoria, valor: Number(c.total), texto: formatCop(c.total) }))}
                  />
                </>
              )}
            </div>
          </div>

          <div className="split">
            <div className="panel">
              <h2>Fijos frente a variables</h2>
              <BarrasHorizontales
                titulo="Gastos según su tipo (COP)"
                items={[
                  { etiqueta: 'Fijos', valor: Number(detalle.gastos_fijos), texto: formatCop(detalle.gastos_fijos) },
                  { etiqueta: 'Variables', valor: Number(detalle.gastos_variables), texto: formatCop(detalle.gastos_variables) },
                ]}
              />
              <p className="muted">Los fijos se repiten cada mes; los variables dependen de tu consumo.</p>
            </div>
            <div className="panel">
              <h2>Meta de ahorro</h2>
              <p className="muted">
                Ahorro logrado <strong>{formatCop(detalle.ahorro_logrado)}</strong> de la meta <strong>{formatCop(detalle.meta_ahorro)}</strong>.
              </p>
              <Progreso
                valor={Number(detalle.meta_ahorro) > 0 ? Math.min(100, (Number(detalle.ahorro_logrado) / Number(detalle.meta_ahorro)) * 100) : 0}
                etiqueta="Avance de la meta de ahorro"
              />
              {Number(detalle.meta_ahorro) === 0 && <p className="muted">Define una meta de ahorro para medir tu avance.</p>}
            </div>
          </div>

          {editando && (
            <form id="edicion-gasto" onSubmit={guardarEdicion} className="panel form-grid" noValidate aria-labelledby="titulo-edicion">
              <h2 id="titulo-edicion" className="form-grid__titulo">Editar gasto</h2>
              <div className="field">
                <label htmlFor="ed-descripcion">Descripción</label>
                <input id="ed-descripcion" value={ed.descripcion} maxLength={CONCEPTO_MAX} onChange={(e) => setEd({ ...ed, descripcion: e.target.value })}
                  aria-invalid={!!errEd.descripcion} aria-describedby={errEd.descripcion ? 'err-ed-descripcion' : undefined} />
                {errEd.descripcion && <p id="err-ed-descripcion" className="field-error">{errEd.descripcion}</p>}
              </div>
              <div className="field">
                <label htmlFor="ed-categoria">Categoría</label>
                <input id="ed-categoria" list="categorias-existentes" value={ed.categoria} maxLength={CATEGORIA_MAX} onChange={(e) => setEd({ ...ed, categoria: e.target.value })}
                  aria-invalid={!!errEd.categoria} aria-describedby={errEd.categoria ? 'err-ed-categoria' : undefined} />
                {errEd.categoria && <p id="err-ed-categoria" className="field-error">{errEd.categoria}</p>}
              </div>
              <div className="field">
                <label htmlFor="ed-monto">Monto (COP)</label>
                <input id="ed-monto" inputMode="decimal" value={ed.monto} onChange={(e) => setEd({ ...ed, monto: e.target.value })}
                  aria-invalid={!!errEd.monto} aria-describedby={errEd.monto ? 'err-ed-monto' : undefined} />
                {errEd.monto && <p id="err-ed-monto" className="field-error">{errEd.monto}</p>}
              </div>
              <div className="field">
                <label htmlFor="ed-tipo">Tipo</label>
                <select id="ed-tipo" value={ed.tipo} onChange={(e) => setEd({ ...ed, tipo: e.target.value as TipoGasto })}>
                  <option value="fijo">Fijo</option>
                  <option value="variable">Variable</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="ed-fecha">Fecha</label>
                <input id="ed-fecha" type="date" min={primerDia(anio, mes)} max={ultimoDia(anio, mes)} value={ed.fecha} onChange={(e) => setEd({ ...ed, fecha: e.target.value })}
                  aria-invalid={!!errEd.fecha} aria-describedby={errEd.fecha ? 'err-ed-fecha' : undefined} />
                {errEd.fecha && <p id="err-ed-fecha" className="field-error">{errEd.fecha}</p>}
              </div>
              <div className="form-actions">
                <button type="submit" className="btn btn--primary">Guardar cambios</button>
                <button type="button" className="btn" onClick={() => setEditando(null)}>Cancelar</button>
              </div>
            </form>
          )}

          <div className="panel">
            <h2>Transacciones del mes</h2>
            {detalle.gastos.length === 0 ? (
              <EstadoVacio titulo="Sin gastos registrados" texto="Registra tu primer gasto con el formulario de arriba." />
            ) : (
              <div className="tabla-wrap">
                <table className="tabla">
                  <caption className="visually-hidden">Gastos del mes {periodoTexto(anio, mes)}</caption>
                  <thead>
                    <tr>
                      <th scope="col">Fecha</th>
                      <th scope="col">Descripción</th>
                      <th scope="col">Categoría</th>
                      <th scope="col">Tipo</th>
                      <th scope="col" className="num">Monto</th>
                      <th scope="col"><span className="visually-hidden">Acciones</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {detalle.gastos.map((g) => (
                      <tr key={g.id} className={editando?.id === g.id ? 'is-editing' : ''}>
                        <td data-label="Fecha">{formatFecha(g.fecha)}</td>
                        <td data-label="Descripción">
                          {g.descripcion} {g.origen === 'demo' && <Badge tono="demo">Demo</Badge>}
                        </td>
                        <td data-label="Categoría">{g.categoria}</td>
                        <td data-label="Tipo"><Badge tono={g.tipo === 'fijo' ? 'muted' : 'ok'}>{g.tipo === 'fijo' ? 'Fijo' : 'Variable'}</Badge></td>
                        <td data-label="Monto" className="num">{formatCop(g.monto)}</td>
                        <td className="acciones">
                          <button type="button" className="btn btn--ghost btn--small" onClick={() => empezarEdicion(g)} aria-label={`Editar ${g.descripcion}`}>
                            <Icono nombre="editar" size={16} /> Editar
                          </button>
                          <BotonConfirmar
                            etiqueta={`Eliminar ${g.descripcion}`}
                            confirmacion={`Se eliminará el gasto «${g.descripcion}» por ${formatCop(g.monto)}.`}
                            onConfirmar={() => void eliminarGasto(g.id, g.descripcion)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
