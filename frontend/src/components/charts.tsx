// Gráficas propias en CSS/SVG (sin librerías). Los valores llegan ya calculados desde el backend.
const PALETA = ['var(--mint)', 'var(--sky)', 'var(--violet)', 'var(--orange)', 'var(--green)', 'var(--red)', '#f6a6d0', '#9be7ff'];

export interface ElementoGrafica {
  etiqueta: string;
  valor: number;
  texto: string; // lo que se muestra en el valor (ya formateado)
}

/** Barras horizontales. Cada barra tiene tooltip (title) y texto accesible. */
export function BarrasHorizontales({ titulo, items, maximo }: { titulo: string; items: ElementoGrafica[]; maximo?: number }) {
  const tope = maximo ?? Math.max(1, ...items.map((i) => i.valor));
  return (
    <figure className="chart" aria-label={titulo}>
      <figcaption className="chart__titulo">{titulo}</figcaption>
      <ul className="bars">
        {items.map((item, indice) => (
          <li key={item.etiqueta} className="bars__fila" title={`${item.etiqueta}: ${item.texto}`}>
            <span className="bars__etiqueta">{item.etiqueta}</span>
            <span className="bars__pista">
              <span
                className="bars__barra"
                style={{ width: `${Math.max(2, (item.valor / tope) * 100)}%`, background: PALETA[indice % PALETA.length] }}
              />
            </span>
            <span className="bars__valor">{item.texto}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Dona con leyenda. Los porcentajes vienen del backend. */
export function Dona({ titulo, items }: { titulo: string; items: { etiqueta: string; porcentaje: number; texto: string }[] }) {
  let acumulado = 0;
  const segmentos = items.map((item, indice) => {
    const inicio = acumulado;
    acumulado += Math.max(0, item.porcentaje);
    return `${PALETA[indice % PALETA.length]} ${inicio}% ${Math.min(100, acumulado)}%`;
  });
  const fondo = items.length ? `conic-gradient(${segmentos.join(', ')})` : 'var(--panel-3)';
  return (
    <figure className="chart chart--dona" aria-label={titulo}>
      <figcaption className="chart__titulo">{titulo}</figcaption>
      <div className="dona-wrap">
        <div className="dona" style={{ background: fondo }} role="img" aria-label={items.map((i) => `${i.etiqueta} ${i.texto}`).join('; ') || 'Sin datos'} />
        <ul className="leyenda">
          {items.map((item, indice) => (
            <li key={item.etiqueta}>
              <span className="leyenda__color" style={{ background: PALETA[indice % PALETA.length] }} aria-hidden="true" />
              <span>{item.etiqueta}</span>
              <span className="leyenda__valor">{item.texto}</span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
