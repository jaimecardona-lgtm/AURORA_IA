// Iconografía propia (trazo 1.8, 24×24). Decorativa salvo que se pase `titulo`.
const RUTAS: Record<string, string> = {
  inicio: 'M3 11.2 12 4l9 7.2V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  libro: 'M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5zM4 19.5A1.5 1.5 0 0 0 5.5 21H20',
  billetera: 'M3 7.5A2.5 2.5 0 0 1 5.5 5H19v4M3 7.5V18a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7H5.5A2.5 2.5 0 0 1 3 7.5z',
  check: 'M4.5 12.5 9 17 19.5 6.5',
  tareas: 'M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2',
  destello: 'M12 3.5l1.9 5.1 5.1 1.9-5.1 1.9L12 17.5l-1.9-5.1-5.1-1.9 5.1-1.9z',
  alerta: 'M12 8.5v4.5m0 3.5h.01M10.3 4.1 2.8 17.4A2 2 0 0 0 4.5 20.5h15a2 2 0 0 0 1.7-3.1L13.7 4.1a2 2 0 0 0-3.4 0z',
  mas: 'M12 5v14M5 12h14',
  editar: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  eliminar: 'M4 7h16M10 11v6M14 11v6M6 7l1-3h10l1 3M6 7l1 13h10l1-13',
  calendario: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  objetivo: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 12h.01',
  grafica: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  reloj: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
  flecha: 'M9 6l6 6-6 6',
  cerrar: 'M6 6l12 12M18 6 6 18',
  menu: 'M4 6h16M4 12h16M4 18h16',
  candado: 'M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3',
};

export type NombreIcono = keyof typeof RUTAS;

export function Icono({ nombre, titulo, size = 20 }: { nombre: NombreIcono; titulo?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="icono"
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
      focusable="false"
    >
      <path d={RUTAS[nombre]} />
    </svg>
  );
}
