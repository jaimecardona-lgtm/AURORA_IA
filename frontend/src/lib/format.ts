// Solo formato para mostrar. Ningún cálculo de negocio vive aquí: los valores llegan del backend.
const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
const nota = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fecha = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });

export const formatCop = (valor: string | number): string => cop.format(Number(valor));
export const formatNota = (valor: string | number | null): string =>
  valor === null || valor === '' ? '—' : nota.format(Number(valor));
export const formatPorcentaje = (valor: string | number): string => `${nota.format(Number(valor))} %`;

/** AAAA-MM-DD (sin zona horaria) -> "12 nov 2026". */
export function formatFecha(iso: string | null): string {
  if (!iso) return 'Sin fecha';
  const [anio, mes, dia] = iso.split('-').map(Number);
  return fecha.format(new Date(anio, mes - 1, dia));
}

export const mesActual = (): { anio: number; mes: number } => {
  const hoy = new Date();
  return { anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 };
};

export const hoyIso = (): string => {
  const hoy = new Date();
  const mm = String(hoy.getMonth() + 1).padStart(2, '0');
  const dd = String(hoy.getDate()).padStart(2, '0');
  return `${hoy.getFullYear()}-${mm}-${dd}`;
};
