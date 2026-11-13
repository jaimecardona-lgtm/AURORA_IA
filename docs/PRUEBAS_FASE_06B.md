# Pruebas — Fase 06B (conexión Supabase)

Fecha: 2026-11-12 · Windows 11 · Python 3.12.10 · Node v22.22.0.

**Resumen honesto:** las pruebas de código están aprobadas. La **integración remota con Supabase no se ha
verificado**: la configuración local apunta a otro proyecto y falta la clave publicable de AURORA_IA. Nada de
lo marcado como «remoto» en este documento se ha ejecutado.

## 1. Resultados ejecutados

| Prueba | Tipo | Resultado |
|---|---|---|
| Pytest completo | Código y simulación | ✅ **228 aprobadas** (218 previas + 10 nuevas del adaptador) |
| Adaptadores PostgREST de Finanzas y Tareas | Simulación en memoria | ✅ 10/10 |
| Cabeceras: clave publicable y JWT del usuario, nunca `service_role` | Simulación | ✅ |
| Sin JWT no se consulta la base | Simulación | ✅ |
| Inserciones sin `user_id` | Simulación | ✅ |
| Importes enviados como cadena decimal exacta | Simulación | ✅ |
| `numeric` llega como `Decimal` exacto (`12345678901234.56`) | Simulación | ✅ |
| Presupuesto, gastos y resumen con el motor | Simulación | ✅ |
| Editar y eliminar gasto | Simulación | ✅ |
| Tareas: CRUD, orden del motor y vencidas | Simulación | ✅ |
| Aislamiento: usuario B no ve ni modifica datos de A | Simulación (no RLS real) | ✅ |
| Error de permiso de la base → 403 | Simulación | ✅ |
| Supabase sin configurar → finanzas y tareas responden 503 | Código | ✅ (`test_finanzas_y_tareas_con_supabase_sin_configurar_responden_503`) |
| Panel general sin Supabase → módulos marcados no disponibles | Código | ✅ |
| Regresión: SQLite, copiloto, motores, API | Código | ✅ |
| Tres CLI del SENA | Ejecución | ✅ exit 0 |
| TypeScript estricto (`tsc --noEmit`) | Compilación | ✅ |
| Build de Vite | Compilación | ✅ |
| Lectura pública del JWKS de AURORA_IA | **Remota (solo lectura)** | ✅ HTTP 200, una clave EC P-256 con ES256 |

Interpretación del JWKS: el backend acepta ES256, así que la verificación de firma sirve con las claves
asimétricas del proyecto. Que se acepte un token real depende de la URL correcta en `backend/.env`.

## 2. Pruebas simuladas (no son integración real)

- **Servidor PostgREST en memoria** (`tests/test_postgrest_dominio.py`): imita filtros `eq.`, orden,
  `return=representation`, `DEFAULT auth.uid()` y la serialización de `numeric`. **No reproduce la política
  RLS de Supabase**. El aislamiento aquí demostrado prueba la lógica del adaptador, no la base real.
- **Transporte HTTP simulado** para el cliente de OpenRouter y el cliente PostgREST (Fase 05 y 06B).

## 3. Bloqueado por configuración (no ejecutado)

| Prueba | Bloqueo |
|---|---|
| Registro de usuarios A y B | Falta crear los usuarios de prueba en el proyecto AURORA_IA (tú) |
| Inicio de sesión real con Supabase Auth | `SUPABASE_URL` de `backend/.env` no es la del proyecto; falta `frontend/.env.local` |
| Persistencia tras recargar y reiniciar con Supabase | Depende del login |
| Aislamiento real A/B con RLS (leer, modificar, eliminar) | Depende de los dos puntos anteriores |
| Dashboard general sobre PostgreSQL | Depende del login y de la base remota verificada |
| Verificación del esquema remoto (`03_verificar_resultado.sql`) | Lo ejecutas tú en el SQL Editor; pendiente de su resultado |

Procedimiento preparado para cuando se desbloquee (no se ha ejecutado):

1. Corregir `SUPABASE_URL` y la clave publicable (ver `FASE_06B_IMPLEMENTACION.md` §5).
2. Pegar aquí el resultado de `03_verificar_resultado.sql`: nueve filas `true`.
3. Con dos usuarios de prueba (credenciales en variables de entorno locales, nunca en el chat):
   - Registro e inicio de sesión de A y de B.
   - Crear datos con A; comprobar que B no los lee ni los cambia (`GET`, `PATCH`, `DELETE` deben devolver vacío o 404).
   - Recargar y reiniciar el servidor; comprobar que los datos de A persisten.
   - Dashboard de A con cifras del motor.

## 4. Defectos encontrados y corregidos en esta fase

| # | Defecto | Cómo se detectó | Corrección |
|---|---|---|---|
| 1 | Los importes se enviaban como `float` a PostgREST | Revisión del flujo de escritura | Servicios pasan cadenas decimales; SQLite convierte solo al escribir |
| 2 | Los `numeric` se leían como `float` | Revisión del cliente | `parse_float=Decimal` en el cliente PostgREST |
| 3 | `backend/.env` con una URL de Supabase que no es la del proyecto | Comprobación de configuración (sin imprimir valores) | No corregido: lo corriges tú (riesgo documentado) |
| 4 | Las pruebas leían `backend/.env` y pasaban a la ruta de Supabase | Fallo de `test_panel_con_supabase...` | Las pruebas fijan las variables de Supabase vacías, que tienen prioridad sobre el archivo |
| 5 | Se eliminó por error la prueba de regresión del hilo de SQLite al editar el archivo | Recuento de pruebas (217 en vez de 218) | Restaurada; la suite vuelve a 218 y luego a 228 |

## 5. Limitaciones

- No hay ninguna prueba remota de login, persistencia ni RLS ejecutada.
- No se ha probado en navegador con Supabase (la prueba de navegador de la Fase 05 usa el modo demo).
- Sin commits, sin despliegue en Render, sin Supabase CLI.
