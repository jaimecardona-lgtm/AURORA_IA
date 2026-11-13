# Fase 01 — Implementación

Primera integración vertical de AURORA AI: **registro/inicio de sesión → token de Supabase →
FastAPI valida el JWT → asignaturas y notas se guardan en Supabase → cierre de sesión → otros
usuarios no ven esos datos.**

Resultados verificados y pendientes: ver [PRUEBAS_FASE_01.md](PRUEBAS_FASE_01.md).

---

## 1. Lo que había al empezar

La auditoría ([ESTADO_INICIAL.md](ESTADO_INICIAL.md)) mostró que el repositorio tenía solo
`README.md` y el documento C4. **No existían** el frontend, el backend, los motores, los CLI, el
Dockerfile ni el `render.yaml` descritos en el prompt. Por eso todo se construyó desde cero, con las
reglas que el prompt especifica.

## 2. Cambios concretos

| Área | Archivos | Qué hace |
|---|---|---|
| Motores | `backend/app/core/grades.py`, `budget.py`, `tasks.py` | Funciones Python puras (sin FastAPI ni BD) para calificaciones, presupuesto COP y priorización de tareas. |
| CLI SENA | `backend/sena_cli/calificaciones.py`, `presupuesto.py`, `tareas.py` | Programas de consola que usan esos motores. Se ejecutan con `python sena_cli/<archivo>.py`. |
| Migración | `supabase/migrations/20261111120000_fase01_dominio_rls.sql` | Tablas del dominio, claves foráneas compuestas, CHECK, índices, RLS forzado, grants y 20 políticas. |
| Pruebas SQL | `supabase/tests/rls_dominio_test.sql`, `supabase/tests/local/00_stub_auth_postgres_local.sql` | 23 comprobaciones de acceso propio, cruzado, anónimo y referencias cruzadas. El stub solo sirve para PostgreSQL local. |
| Seguridad | `backend/app/security/jwt_verifier.py` | Verifica firma (JWKS), iss, aud, exp, iat, sub. Solo RS256/ES256. |
| Acceso a datos | `backend/app/repositories/postgrest_client.py`, `academic_repository.py` | Llama a PostgREST con el JWT del usuario y traduce errores de Postgres a HTTP. |
| Lógica | `backend/app/services/academic_service.py` | Promedios con el motor y 404 cuando RLS oculta un registro. |
| DTO | `backend/app/schemas/academic.py` | Pydantic con `extra="forbid"`. Las notas se validan con el motor. |
| API | `backend/app/api/deps.py`, `routes_academic.py`, `backend/app/main.py` | Endpoints REST bajo `/api`, `/api/health`, `/api/docs` y servido del SPA. |
| Configuración | `backend/app/config.py`, `backend/.env.example`, `frontend/.env.example` | Variables de entorno con valores ficticios. |
| Pruebas Python | `backend/tests/*.py` (89 pruebas) | Motores, JWT, API, cliente PostgREST y CLI. |
| Frontend | `frontend/src/**` | Acceso y registro, shell con navegación, módulo Académico, módulos pendientes. |
| Pruebas de UI | `frontend/e2e/*.py` | Pruebas de humo con Playwright (opcionales). |
| Empaquetado | `Dockerfile`, `.dockerignore`, `render.yaml` | Imagen única y blueprint de Render. **No desplegado.** |
| Repositorio | `.gitignore`, `README.md`, `docs/*` | Exclusión de secretos e instrucciones de instalación. |

No se modificó ningún archivo existente del usuario. `AURORA_AI_Arquitectura_C4.html` se **copió** a
`docs/arquitectura-c4.html` y el original quedó igual.

## 3. Decisiones técnicas

Cada decisión indica su impacto en seguridad (S), mantenibilidad (M) y aprendizaje (A).

| # | Decisión | Por qué | Impacto |
|---|---|---|---|
| D1 | Motores **desde cero** en lugar de "conservar" | El prototipo no existe en el repositorio (verificado). | M: funciones puras, probadas y reutilizables por la API y la CLI. A: se ven las reglas de negocio sin framework. |
| D2 | Prioridad de tareas: **1 = alta, 2 = media, 3 = baja** | El prompt indica 1..3 sin sentido. Se documenta para que el equipo lo confirme. | M: un solo punto de cambio en `tasks.py`. |
| D3 | Aritmética con `Decimal` | Los `float` introducen errores al comparar con 3.0 y al promediar. | S/M: el umbral 3.0 es exacto. |
| D4 | **JWKS asimétrico**; se rechaza HS256 y `none` | Con HS256 la clave pública podría usarse como secreto (confusión de algoritmos). | S: alta. Exige claves de firma asimétricas en Supabase (ver README). |
| D5 | Validación del JWT en FastAPI **y** RLS en la base de datos | Dos capas independientes: si una falla, la otra protege los datos. | S: alta. |
| D6 | El backend llama a PostgREST **con el JWT del usuario** | RLS aplica `auth.uid()` sin que el backend tenga privilegios de administrador. | S: alta. A: se entiende la propagación de identidad. |
| D7 | Sin ORM ni driver SQL: cliente HTTP a PostgREST | Evita manejar conexiones con privilegios y mantiene todo bajo RLS. | S/M: menos piezas. Limitación: sin joins complejos (aceptable en esta fase). |
| D8 | `user_id` con `DEFAULT auth.uid()` y **sin** campo en la API | El cliente no puede elegir de quién es el dato. Además, `extra="forbid"` rechaza ese campo si se envía. | S: alta. |
| D9 | **Claves foráneas compuestas** `(user_id, subject_id)` | Impiden que la nota de B apunte a la asignatura de A aunque RLS oculte la fila. | S: alta. Verificado en la prueba RLS. |
| D10 | `FORCE ROW LEVEL SECURITY` y grants solo a `authenticated` | Ni el dueño de la tabla ni `anon` acceden sin política. | S: alta. |
| D11 | Errores: 401, 403, 404, 422, **409** (duplicados) y 503 | 409 se añade a lo pedido porque un duplicado no es un 422 ni un 404. | M: códigos coherentes. |
| D12 | El código SQLSTATE manda sobre el HTTP status en PostgREST | PostgREST devuelve 409 para FK y UNIQUE. Se detectó con prueba y se corrigió. | M: mapeo exacto. |
| D13 | Sin backend si falta configuración: **503**, no 500 | Un fallo de configuración no debe parecer un error de código. | M: diagnóstico claro. |
| D14 | Frontend: `supabase-js` **solo para Auth** | Los datos de negocio no se leen desde el navegador. | S: alta. |
| D15 | `signOut` global con respaldo a local | Sin red, `global` conserva la sesión en el dispositivo. Verificado con la UI. | S/M: el usuario siempre puede salir. |
| D16 | Navegación por estado, sin React Router | Hay cuatro módulos. Una dependencia menos. | M: más simple. |
| D17 | Finanzas, Tareas y Copiloto marcados **Pendiente** | El prompt pide no aparentar persistencia. | S/A: honestidad del estado. |
| D18 | Un solo Web Service con API y SPA en el mismo origen | Sin CORS en producción y una sola URL. | S/M: menos superficie. |

## 4. Recorrido del flujo (para aprender)

```
 Navegador (React)                 FastAPI (backend)                       Supabase
 ─────────────────                 ─────────────────                       ────────
1. Usuario escribe correo y
   contraseña.
2. supabase.auth.signIn… ───────────────────────────────────────────────▶ Auth emite JWT
                                                                          (firmado, exp ~1 h)
3. Recibe access_token. ◀──────────────────────────────────────────────────
4. fetch('/api/subjects',
     Authorization: Bearer JWT) ─▶ 5. get_auth_context():
                                      - falta Bearer  → 401
                                      - firma/iss/aud/exp → 401
                                      - JWKS no responde → 503
                                      - válido → AuthContext(user, token)
                                   6. AcademicService → Repository
                                   7. PostgREST con Authorization:
                                      Bearer JWT (el del usuario) ───────▶ 8. RLS:
                                                                              auth.uid() = user_id
                                                                              filtra y valida filas
                                   9. ◀──── JSON solo con filas propias ──────
                                   10. Calcula promedio con el motor
                                       y responde DTO.
11. Renderiza la tabla y el
    promedio. ◀─────────────────────
12. Cerrar sesión → signOut()
    elimina la sesión local.
```

Puntos clave:
- **Dos capas de autorización**: FastAPI rechaza tokens inválidos (401) y PostgreSQL filtra filas
  por usuario (RLS). Si el código de la API tuviera un fallo, la base de datos seguiría protegiendo los datos.
- **El backend no es administrador**: no usa `service_role`. Propaga el token del usuario.
- **La interfaz no decide la identidad**: el `user_id` lo pone `auth.uid()` en la base de datos.

## 5. Cómo reproducir

Ver [README.md](../README.md). Los comandos con salida real están en
[PRUEBAS_FASE_01.md](PRUEBAS_FASE_01.md).

## 6. Riesgos abiertos

1. **Sin proyecto Supabase real**: el registro, el inicio de sesión y las consultas con datos reales no se han probado. Es la prueba más importante pendiente.
2. **Claves de firma**: si el proyecto usa solo HS256 heredado, el backend rechazará todos los tokens (401). Hay que activar claves asimétricas.
3. **Docker y Render no verificados**: el daemon de Docker no estaba activo. El despliegue no se ha hecho.
4. **Migración en producción**: se aplica manualmente o con la CLI. No hay pipeline de migraciones automático.
5. **Prioridad de tareas**: la semántica 1 = alta debe confirmarse con el equipo.
6. **Sin límite de peticiones** en la API: pendiente para una fase de endurecimiento.

## 7. Siguiente prompt recomendado

**Fase 02 — Conexión real con Supabase y primer despliegue controlado**: crear el proyecto,
aplicar la migración, ejecutar las pruebas RLS en el SQL Editor, probar login/registro/recarga/logout
con una cuenta de prueba, y después desplegar en Render con la URL y la comprobación de `/api/health`.
