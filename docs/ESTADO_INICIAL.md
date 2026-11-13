# Estado inicial del repositorio AURORA_IA

Fecha de auditoría: 2026-11-11 (entorno Windows 11, Git Bash / PowerShell).

## 1. Observado (evidencia)

| Elemento solicitado en el prompt | Estado real | Evidencia |
|---|---|---|
| Git: rama activa | `main` | `git branch --show-current` |
| Git: historial | Un único commit `9ae034f Initial commit` | `git log --oneline` |
| Git: estado de trabajo | Solo `?? AURORA_AI_Arquitectura_C4.html` (sin trackear) | `git status --short` |
| Contenido versionado | Solo `README.md` (contenido: `# AURORA_IA`) | `git ls-files` |
| `frontend/` (React + Vite) | **No existe** | `ls frontend` → inexistente |
| `backend/` (FastAPI) | **No existe** | `ls backend` → inexistente |
| `backend/app/core/` (motores calificaciones, presupuesto, tareas) | **No existe** | búsqueda de `calificaciones*.py`, `presupuesto*.py`, `sena_cli` en `GitHub/` → sin resultados |
| `backend/sena_cli/` | **No existe** | ídem |
| `backend/tests/` | **No existe** | ídem |
| `Dockerfile`, `render.yaml` | **No existen** | `ls -la` en la raíz |
| `package.json`, `requirements.txt`, `.env.example`, `.gitignore` | **No existen** | `ls -la`; `cat .gitignore` → no existe |
| `docs/arquitectura-c4.html` | **No existe** en esa ruta. Existe `AURORA_AI_Arquitectura_C4.html` en la raíz (sin trackear) | `ls -la` |
| Prototipo en otras carpetas de `GitHub/` | Ninguna carpeta contiene el prototipo de AURORA (solo `AURORA_IA` vacío y `sena-mongodb-mundial-2018`, no relacionado) | `ls -d *AURORA* *sena*` |
| `python -m pytest -q` | `no tests ran` (no hay tests) | salida real en la auditoría |
| `npm run build` | `npm error enoent` (no hay `package.json`) | salida real en la auditoría |
| Docker | Instalado (27.2.0) pero **daemon apagado** (`dockerDesktopLinuxEngine` no disponible) | `docker info` |
| PostgreSQL local | Cliente `psql` 18.6 instalado; **no hay servidor** escuchando en `localhost:5432` | `pg_isready`/conexión |
| Herramientas | Node v22.22.0, npm 10.6.0, Python 3.11.9 y 3.12.10, Git 2.52.0, Supabase CLI 2.48.3 | `--version` |

## 2. Componentes reutilizables

- **Ninguno verificable.** No hay código de motores, CLI ni interfaz que reutilizar. Por eso los motores de calificaciones, presupuesto y tareas se implementan **desde cero** según las reglas del prompt (escala 0–5, aprobación ≥ 3.0, presupuesto en COP, prioridad 1..3).
- Reutilizable: el documento de arquitectura `AURORA_AI_Arquitectura_C4.html` (copiado, no movido, a `docs/arquitectura-c4.html`). Es HTML autocontenido con estilo oscuro, útil como referencia visual para el dashboard.

## 3. Funcionalidades simuladas o persistidas en localStorage

- No hay código, por lo tanto **no hay persistencia en localStorage que migrar** ni funcionalidades simuladas que retirar.
- El documento C4 es estático (no simula datos de negocio).

## 4. Riesgos de seguridad observados

- Riesgo de **arranque sin nada versionado**: sin `.gitignore`, un `.env` real podría subirse por accidente. Mitigación: crear `.gitignore` antes de cualquier archivo de configuración (incluido en esta fase).
- Riesgo futuro de **confiar en `user_id` del JSON**: se mitiga con validación criptográfica del JWT en FastAPI y RLS con `auth.uid()` en Supabase.
- Riesgo de **usar `service_role` en el navegador o bypass de RLS**: se prohíbe en la arquitectura y se documenta.
- El documento C4 sí referencia OpenRouter; **no se activará en esta fase** (sin claves, sin endpoints).

## 5. Errores y deuda técnica

- Ausencia total de pruebas, empaquetado y configuración de despliegue.
- Ausencia de migraciones: el modelo de datos no existe todavía.
- El documento C4 está fuera de `docs/` (ubicación no estándar para el proyecto).
- No hay evidencia de que el prototipo mencionado en el prompt haya existido en este repositorio; el prompt indica explícitamente "no supongas que todo existe", y la auditoría confirma que no existe.

## 6. Pendiente

- Crear desde cero: frontend, backend, migraciones, pruebas, Docker y Render (sin desplegar).
- Conectar con un proyecto Supabase real: **no disponible** en esta sesión (sin URL, sin claves, sin cuenta de prueba). Pendiente explícito del usuario.
- Ejecutar pruebas RLS contra PostgreSQL real: Docker apagado y sin servidor PostgreSQL local. Ver `docs/PRUEBAS_FASE_01.md` para el estado.

## 7. Decisiones

1. **Construir los motores desde cero** en lugar de "conservarlos", porque no existen. Se documenta como desviación del prompt. Se mantienen como funciones Python puras, sin dependencias de FastAPI, y con un programa CLI por motor en `backend/sena_cli/`.
2. **Estructura monorepo** según el prompt: `frontend/`, `backend/`, `supabase/migrations/`, `supabase/tests/`, `docs/`.
3. **Archivo C4**: se copia a `docs/arquitectura-c4.html`; el original en la raíz se conserva sin cambios.
4. **No se hace commit, push ni despliegue** (instrucción explícita del prompt).
5. **Nada de OpenRouter** en esta fase.
6. **Verificación RLS**: se escriben pruebas SQL ejecutables en Supabase; su ejecución real queda pendiente si no hay una base de datos disponible.
