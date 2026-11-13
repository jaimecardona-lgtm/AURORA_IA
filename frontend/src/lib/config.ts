// Base de la API: vacío = mismo origen (producción en Render y proxy de Vite en desarrollo).
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
