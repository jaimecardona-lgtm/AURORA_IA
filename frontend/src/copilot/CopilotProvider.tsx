import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { copilotApi, type EstadoCopiloto, type Inclusiones, type RespuestaCopiloto, type Turno } from '../api/copilot';
import {
  conversacionesApi,
  respuestaDesdeRemoto,
  TAMANO_PAGINA_CONVERSACIONES,
  TAMANO_PAGINA_MENSAJES,
  type ConversacionRemota,
  type MensajeRemoto,
} from '../api/conversaciones';
import { ApiError } from '../api/http';

/**
 * Estado ÚNICO del copiloto, compartido por la página completa y el widget flotante.
 *
 * Dos modos, decididos por el servidor (`estado.persistencia`):
 * - Persistencia activa (migración 08A aplicada): las conversaciones y los mensajes se guardan en la cuenta del usuario.
 *   Al recargar se recupera el historial. Cada envío se guarda con un identificador de cliente (idempotente).
 * - Sin persistencia (por defecto): todo vive solo en memoria de esta pestaña. La interfaz no lo presenta como guardado.
 *
 * Comunes a ambos modos:
 * - Se reinician al cambiar de cuenta (userKey). Las respuestas de una cuenta anterior se descartan.
 * - Solo se envía al modelo el historial de la conversación activa, en intercambios completos.
 * - Un único envío a la vez.
 * - Ningún JWT ni secreto se guarda en los mensajes: las peticiones pasan por el cliente HTTP existente.
 */

const TITULO_POR_DEFECTO = 'Nueva conversación';

type MensajeUsuario = { id: number; rol: 'user'; texto: string; clienteId: string; remoteId?: string };

export type Mensaje =
  | MensajeUsuario
  | { id: number; rol: 'assistant'; texto: string; respuesta: RespuestaCopiloto; remoteId?: string }
  | {
      id: number;
      rol: 'error';
      texto: string;
      /** Paso que falló: 'usuario' (guardar la pregunta), 'consulta' (modelo) o 'guardar' (guardar la respuesta). */
      tipo: 'usuario' | 'consulta' | 'guardar';
      pregunta: string;
      incluir: Inclusiones;
      mensajeUsuarioId: number;
      respuesta?: RespuestaCopiloto;
      clienteAsistente?: string;
    };

export interface Conversacion {
  id: number;
  remoteId?: string;
  titulo: string;
  mensajes: Mensaje[];
  /** true cuando los mensajes ya están cargados (en modo sin persistencia, siempre). */
  cargada: boolean;
  cargando: boolean;
}

interface CopilotState {
  estado: EstadoCopiloto | null;
  errorEstado: string | null;
  /** Aviso de la conversación (p. ej. fallo al cargar o al renombrar). No sustituye a la página. */
  aviso: string | null;
  descartarAviso: () => void;
  persistencia: boolean;
  cargando: boolean;
  hayMasConversaciones: boolean;
  cargarMasConversaciones: () => void;
  conversaciones: Conversacion[];
  activaId: number;
  mensajes: Mensaje[];
  pendiente: boolean;
  incluir: Inclusiones;
  abierto: boolean;
  setIncluir: (i: Inclusiones) => void;
  setAbierto: (abierto: boolean) => void;
  enviar: (texto: string) => void;
  reintentar: (mensajeId: number) => void;
  nueva: () => void;
  seleccionar: (id: number) => void;
  limpiar: () => void;
}

const CopilotContext = createContext<CopilotState | null>(null);
const LIMITE_HISTORIAL = 6;

let contadorLocal = 1;
const nuevoId = (): number => contadorLocal++;

function generarId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function errorDe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return 'No se pudo obtener la respuesta. Revisa tu conexión e intenta de nuevo.';
}

function tituloDe(texto: string): string {
  const limpio = texto.replace(/\s+/g, ' ').trim();
  return limpio.length > 42 ? `${limpio.slice(0, 42)}…` : limpio;
}

/** Solo intercambios completos (pregunta seguida de respuesta). Las preguntas sin respuesta no se envían. */
function historialDe(mensajes: Mensaje[]): Turno[] {
  const turnos: Turno[] = [];
  for (let i = 0; i < mensajes.length - 1; i++) {
    const actual = mensajes[i];
    const siguiente = mensajes[i + 1];
    if (actual.rol === 'user' && siguiente.rol === 'assistant') {
      turnos.push({ role: 'user', content: actual.texto });
      turnos.push({ role: 'assistant', content: siguiente.texto });
      i++;
    }
  }
  return turnos.slice(-LIMITE_HISTORIAL);
}

const nuevaLocal = (): Conversacion => ({ id: nuevoId(), titulo: TITULO_POR_DEFECTO, mensajes: [], cargada: true, cargando: false });

const localDesdeRemoto = (r: ConversacionRemota): Conversacion => ({
  id: nuevoId(),
  remoteId: r.id,
  titulo: r.title,
  mensajes: [],
  cargada: false,
  cargando: false,
});

function desdeRemoto(m: MensajeRemoto): Mensaje {
  return m.role === 'user'
    ? { id: nuevoId(), rol: 'user', texto: m.content, clienteId: m.cliente_id, remoteId: m.id }
    : { id: nuevoId(), rol: 'assistant', texto: m.content, respuesta: respuestaDesdeRemoto(m), remoteId: m.id };
}

export function CopilotProvider({ userKey, children }: { userKey: string; children: ReactNode }) {
  const [estado, setEstado] = useState<EstadoCopiloto | null>(null);
  const [errorEstado, setErrorEstado] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [conversaciones, setConversaciones] = useState<Conversacion[]>([]);
  const [activaId, setActivaId] = useState(0);
  const [pendiente, setPendiente] = useState(false);
  const [cargandoLista, setCargandoLista] = useState(false);
  const [siguienteListado, setSiguienteListado] = useState<number | null>(null);
  const [incluir, setIncluir] = useState<Inclusiones>({ academic: true, finance: true, tasks: true });
  const [abierto, setAbierto] = useState(false);

  const pendienteRef = useRef(false);
  const generacion = useRef(0); // invalida respuestas de una cuenta anterior
  const conversacionesRef = useRef<Conversacion[]>([]);
  conversacionesRef.current = conversaciones;
  const persistente = estado?.persistencia === true;
  const persistenteRef = useRef(false);
  persistenteRef.current = persistente;

  // ----- actualizaciones de estado (siempre sobre la versión más reciente) -----
  const editarConversacion = useCallback((id: number, fn: (c: Conversacion) => Conversacion) => {
    setConversaciones((prev) => prev.map((c) => (c.id === id ? fn(c) : c)));
  }, []);
  const añadirMensaje = useCallback(
    (convId: number, m: Mensaje) => editarConversacion(convId, (c) => ({ ...c, mensajes: [...c.mensajes, m] })),
    [editarConversacion],
  );
  const reemplazarMensaje = useCallback(
    (convId: number, mensajeId: number, cambios: Partial<Mensaje>) =>
      editarConversacion(convId, (c) => ({
        ...c,
        mensajes: c.mensajes.map((m) => (m.id === mensajeId ? ({ ...m, ...cambios } as Mensaje) : m)),
      })),
    [editarConversacion],
  );
  const quitarMensaje = useCallback(
    (convId: number, mensajeId: number) =>
      editarConversacion(convId, (c) => ({ ...c, mensajes: c.mensajes.filter((m) => m.id !== mensajeId) })),
    [editarConversacion],
  );

  // ----- carga desde el servidor (solo con persistencia) -----
  const cargarMensajesRemotos = useCallback(
    async (convId: number, remoteId: string, gen: number) => {
      editarConversacion(convId, (c) => ({ ...c, cargando: true }));
      try {
        const mensajes: Mensaje[] = [];
        let desplazamiento: number | null = 0;
        while (desplazamiento !== null) {
          const pagina = await conversacionesApi.mensajes(remoteId, TAMANO_PAGINA_MENSAJES, desplazamiento);
          if (gen !== generacion.current) return;
          mensajes.push(...pagina.items.map(desdeRemoto));
          desplazamiento = pagina.siguiente;
        }
        if (gen !== generacion.current) return;
        editarConversacion(convId, (c) => ({ ...c, mensajes, cargada: true, cargando: false }));
      } catch (e) {
        if (gen !== generacion.current) return;
        editarConversacion(convId, (c) => ({ ...c, cargando: false }));
        setAviso(errorDe(e));
      }
    },
    [editarConversacion],
  );

  const cargarInicialRemoto = useCallback(
    async (gen: number) => {
      setCargandoLista(true);
      try {
        const pagina = await conversacionesApi.listar(TAMANO_PAGINA_CONVERSACIONES, 0);
        if (gen !== generacion.current) return;
        let remotas = pagina.items;
        if (remotas.length === 0) remotas = [await conversacionesApi.crear()];
        if (gen !== generacion.current) return;
        const locales = remotas.map(localDesdeRemoto);
        setConversaciones(locales);
        setActivaId(locales[0].id);
        setSiguienteListado(pagina.siguiente);
        await cargarMensajesRemotos(locales[0].id, locales[0].remoteId ?? '', gen);
      } catch (e) {
        if (gen === generacion.current) setAviso(errorDe(e));
      } finally {
        if (gen === generacion.current) setCargandoLista(false);
      }
    },
    [cargarMensajesRemotos],
  );

  // Reinicio completo al cambiar de cuenta (y por tanto al cerrar sesión).
  useEffect(() => {
    generacion.current += 1;
    pendienteRef.current = false;
    setPendiente(false);
    setAbierto(false);
    setAviso(null);
    setConversaciones([]);
    setActivaId(0);
    setSiguienteListado(null);
    setEstado(null);
    setErrorEstado(null);
    const gen = generacion.current;
    copilotApi
      .estado()
      .then(async (e) => {
        if (gen !== generacion.current) return;
        setEstado(e);
        if (e.persistencia) {
          await cargarInicialRemoto(gen);
        } else {
          const inicial = nuevaLocal();
          setConversaciones([inicial]);
          setActivaId(inicial.id);
        }
      })
      .catch((e) => gen === generacion.current && setErrorEstado(errorDe(e)));
  }, [userKey, cargarInicialRemoto]);

  // ----- envío en varios pasos ------------------------------------------------
  /**
   * Pasos: 'usuario' (guardar la pregunta, solo con persistencia), 'consulta' (modelo) y 'guardar' (guardar la respuesta).
   * Cada fallo queda como mensaje de error con el paso que falló, para reintentar solo ese paso.
   */
  const ejecutar = useCallback(
    async (
      convId: number,
      mensajeUsuario: MensajeUsuario,
      inc: Inclusiones,
      pasoInicial: 'usuario' | 'consulta' | 'guardar',
      extra?: { respuesta?: RespuestaCopiloto; clienteAsistente?: string; primeraPregunta?: boolean },
    ) => {
      const gen = generacion.current;
      const vigente = () => gen === generacion.current;
      const remoto = persistenteRef.current;
      const fallo = (tipo: 'usuario' | 'consulta' | 'guardar', e: unknown, respuesta?: RespuestaCopiloto, clienteAsistente?: string): Mensaje => ({
        id: nuevoId(),
        rol: 'error',
        texto: errorDe(e),
        tipo,
        pregunta: mensajeUsuario.texto,
        incluir: inc,
        mensajeUsuarioId: mensajeUsuario.id,
        respuesta,
        clienteAsistente,
      });

      pendienteRef.current = true;
      setPendiente(true);
      try {
        const remoteId = conversacionesRef.current.find((c) => c.id === convId)?.remoteId;
        let paso = pasoInicial;
        let respuesta = extra?.respuesta;
        let clienteAsistente = extra?.clienteAsistente;

        if (paso === 'usuario') {
          try {
            const r = await conversacionesApi.guardarMensaje(remoteId ?? '', {
              cliente_id: mensajeUsuario.clienteId,
              role: 'user',
              content: mensajeUsuario.texto,
            });
            if (!vigente()) return;
            reemplazarMensaje(convId, mensajeUsuario.id, { remoteId: r.mensaje.id });
            if (extra?.primeraPregunta) {
              // Título derivado de la primera pregunta (no bloquea el envío; un fallo se ignora).
              conversacionesApi.renombrar(remoteId ?? '', tituloDe(mensajeUsuario.texto)).catch(() => undefined);
            }
          } catch (e) {
            if (vigente()) añadirMensaje(convId, fallo('usuario', e));
            return;
          }
          paso = 'consulta';
        }

        if (paso === 'consulta') {
          const actuales = conversacionesRef.current.find((c) => c.id === convId)?.mensajes ?? [];
          const indice = actuales.findIndex((m) => m.id === mensajeUsuario.id);
          const historial = historialDe(indice > 0 ? actuales.slice(0, indice) : []);
          const r = await copilotApi.chat(mensajeUsuario.texto, historial, inc);
          if (!vigente()) return;
          respuesta = r;
          clienteAsistente = generarId();
          paso = 'guardar';
        }

        if (!respuesta) return;
        if (!remoto) {
          añadirMensaje(convId, { id: nuevoId(), rol: 'assistant', texto: respuesta.answer, respuesta });
          return;
        }
        try {
          const r = await conversacionesApi.guardarMensaje(remoteId ?? '', {
            cliente_id: clienteAsistente ?? generarId(),
            role: 'assistant',
            content: respuesta.answer,
            estado: respuesta.incomplete ? 'incompleto' : 'completado',
            proveedor: respuesta.provider,
            modelo: respuesta.model,
            simulado: respuesta.simulado,
            contexto_usado: respuesta.context_used,
            total_tokens: respuesta.usage.total_tokens,
          });
          if (!vigente()) return;
          añadirMensaje(convId, { id: nuevoId(), rol: 'assistant', texto: respuesta.answer, respuesta, remoteId: r.mensaje.id });
        } catch (e) {
          if (vigente()) añadirMensaje(convId, fallo('guardar', e, respuesta, clienteAsistente));
        }
      } catch (e) {
        // Fallo del modelo (o inesperado en el paso de consulta).
        if (vigente()) añadirMensaje(convId, fallo('consulta', e));
      } finally {
        if (vigente()) {
          pendienteRef.current = false;
          setPendiente(false);
        }
      }
    },
    [añadirMensaje, reemplazarMensaje],
  );

  const enviar = useCallback(
    (texto: string) => {
      const pregunta = texto.trim();
      if (!pregunta || pendienteRef.current || !estado?.configurado) return;
      const conv = conversacionesRef.current.find((c) => c.id === activaId);
      if (!conv || conv.cargando) return;
      if (persistenteRef.current && (!conv.cargada || !conv.remoteId)) return;
      const primeraPregunta = !conv.mensajes.some((m) => m.rol === 'user');
      const mensajeUsuario: MensajeUsuario = { id: nuevoId(), rol: 'user', texto: pregunta, clienteId: generarId() };
      añadirMensaje(conv.id, mensajeUsuario);
      if (primeraPregunta && conv.titulo === TITULO_POR_DEFECTO) {
        editarConversacion(conv.id, (c) => ({ ...c, titulo: tituloDe(pregunta) }));
      }
      void ejecutar(conv.id, mensajeUsuario, incluir, persistenteRef.current ? 'usuario' : 'consulta', { primeraPregunta });
    },
    [activaId, estado, incluir, añadirMensaje, editarConversacion, ejecutar],
  );

  const reintentar = useCallback(
    (mensajeId: number) => {
      if (pendienteRef.current) return;
      const conv = conversacionesRef.current.find((c) => c.id === activaId);
      const error = conv?.mensajes.find((m) => m.id === mensajeId);
      if (!conv || !error || error.rol !== 'error') return;
      const mensajeUsuario = conv.mensajes.find((m): m is MensajeUsuario => m.id === error.mensajeUsuarioId && m.rol === 'user');
      if (!mensajeUsuario) return;
      quitarMensaje(conv.id, error.id);
      void ejecutar(conv.id, mensajeUsuario, error.incluir, error.tipo, {
        respuesta: error.respuesta,
        clienteAsistente: error.clienteAsistente,
      });
    },
    [activaId, quitarMensaje, ejecutar],
  );

  const nueva = useCallback(() => {
    if (pendienteRef.current) return;
    const gen = generacion.current;
    if (!persistenteRef.current) {
      const c = nuevaLocal();
      setConversaciones((prev) => [c, ...prev]);
      setActivaId(c.id);
      return;
    }
    conversacionesApi
      .crear()
      .then((r) => {
        if (gen !== generacion.current) return;
        const c = localDesdeRemoto(r);
        c.cargada = true;
        setConversaciones((prev) => [c, ...prev]);
        setActivaId(c.id);
      })
      .catch((e) => gen === generacion.current && setAviso(errorDe(e)));
  }, []);

  const seleccionar = useCallback(
    (id: number) => {
      if (pendienteRef.current) return;
      setActivaId(id);
      const conv = conversacionesRef.current.find((c) => c.id === id);
      if (persistenteRef.current && conv && !conv.cargada && !conv.cargando && conv.remoteId) {
        void cargarMensajesRemotos(id, conv.remoteId, generacion.current);
      }
    },
    [cargarMensajesRemotos],
  );

  const limpiar = useCallback(() => {
    if (pendienteRef.current) return;
    const conv = conversacionesRef.current.find((c) => c.id === activaId);
    if (!conv) return;
    if (!persistenteRef.current) {
      editarConversacion(activaId, (c) => ({ ...c, mensajes: [], titulo: TITULO_POR_DEFECTO }));
      return;
    }
    // Con persistencia, «limpiar» elimina la conversación de la cuenta: pide confirmación explícita.
    if (!conv.remoteId || !window.confirm('¿Eliminar esta conversación? Se borrarán sus mensajes y no se puede deshacer.')) return;
    const gen = generacion.current;
    conversacionesApi
      .eliminar(conv.remoteId)
      .then(() => conversacionesApi.crear())
      .then((r) => {
        if (gen !== generacion.current) return;
        const nueva = localDesdeRemoto(r);
        nueva.cargada = true;
        setConversaciones((prev) => [nueva, ...prev.filter((c) => c.id !== conv.id)]);
        setActivaId(nueva.id);
      })
      .catch((e) => gen === generacion.current && setAviso(errorDe(e)));
  }, [activaId, editarConversacion]);

  const cargarMasConversaciones = useCallback(() => {
    if (siguienteListado === null || pendienteRef.current) return;
    const gen = generacion.current;
    conversacionesApi
      .listar(TAMANO_PAGINA_CONVERSACIONES, siguienteListado)
      .then((pagina) => {
        if (gen !== generacion.current) return;
        const nuevas = pagina.items.map(localDesdeRemoto);
        setConversaciones((prev) => [...prev, ...nuevas]);
        setSiguienteListado(pagina.siguiente);
      })
      .catch((e) => gen === generacion.current && setAviso(errorDe(e)));
  }, [siguienteListado]);

  const descartarAviso = useCallback(() => setAviso(null), []);

  const valor = useMemo<CopilotState>(() => {
    const activa = conversaciones.find((c) => c.id === activaId);
    return {
      estado,
      errorEstado,
      aviso,
      descartarAviso,
      persistencia: persistente,
      cargando: cargandoLista || (activa?.cargando ?? false),
      hayMasConversaciones: siguienteListado !== null,
      cargarMasConversaciones,
      conversaciones,
      activaId,
      mensajes: activa?.mensajes ?? [],
      pendiente,
      incluir,
      abierto,
      setIncluir,
      setAbierto,
      enviar,
      reintentar,
      nueva,
      seleccionar,
      limpiar,
    };
  }, [
    estado, errorEstado, aviso, descartarAviso, persistente, cargandoLista, siguienteListado, cargarMasConversaciones,
    conversaciones, activaId, pendiente, incluir, abierto, enviar, reintentar, nueva, seleccionar, limpiar,
  ]);

  return <CopilotContext.Provider value={valor}>{children}</CopilotContext.Provider>;
}

export function useCopilot(): CopilotState {
  const ctx = useContext(CopilotContext);
  if (!ctx) throw new Error('useCopilot debe usarse dentro de CopilotProvider');
  return ctx;
}
