import { apiRequest } from './http';

// Tipos que espejan los DTO de backend/app/schemas/academic.py.
// Los decimales llegan como cadenas (Pydantic serializa Decimal como string).
export type Origen = 'real' | 'demo';

export interface Subject {
  id: string;
  nombre: string;
  origen: Origen;
  created_at: string;
  updated_at: string;
  total_notas: number;
  promedio: string | null;
  aprobado: boolean | null;
}

export interface Grade {
  id: string;
  subject_id: string;
  descripcion: string;
  nota: string;
  aprobado: boolean;
  origen: Origen;
  created_at: string;
  updated_at: string;
}

export interface SubjectDetail extends Subject {
  notas: Grade[];
}

export interface NotaNecesaria {
  objetivo: string;
  posible: boolean;
  nota_minima: string | null;
  mensaje: string;
}

export interface ResumenAcademico {
  total_asignaturas: number;
  con_notas: number;
  aprobadas: number;
  reprobadas: number;
  promedio_general: string | null;
}

export const academicApi = {
  listSubjects: () => apiRequest<Subject[]>('GET', '/api/subjects'),
  createSubject: (nombre: string) => apiRequest<Subject>('POST', '/api/subjects', { nombre }),
  renameSubject: (id: string, nombre: string) => apiRequest<Subject>('PATCH', `/api/subjects/${id}`, { nombre }),
  getSubject: (id: string) => apiRequest<SubjectDetail>('GET', `/api/subjects/${id}`),
  deleteSubject: (id: string) => apiRequest<void>('DELETE', `/api/subjects/${id}`),
  addGrade: (subjectId: string, descripcion: string, nota: number) =>
    apiRequest<Grade>('POST', `/api/subjects/${subjectId}/grades`, { descripcion, nota }),
  updateGrade: (gradeId: string, cambios: { descripcion?: string; nota?: number }) =>
    apiRequest<Grade>('PATCH', `/api/grades/${gradeId}`, cambios),
  deleteGrade: (gradeId: string) => apiRequest<void>('DELETE', `/api/grades/${gradeId}`),
  notaNecesaria: (subjectId: string, objetivo: number) =>
    apiRequest<NotaNecesaria>('GET', `/api/subjects/${subjectId}/objetivo?objetivo=${objetivo}`),
  resumen: () => apiRequest<ResumenAcademico>('GET', '/api/academico/resumen'),
};
