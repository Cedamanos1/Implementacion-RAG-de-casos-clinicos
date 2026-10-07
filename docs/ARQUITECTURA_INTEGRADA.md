# Arquitectura integrada EN-002 + RAG

## Recuperación entre múltiples casos

Frontend / selector
→ FastAPI
→ `/api/v1/rag/cases/search`
→ filtro de especialidad
→ embeddings + índice RAG
→ candidatos por `case_id`
→ selección de un caso

## Recuperación dentro de una sesión

StateGraph
→ `case_id` activo
→ política de contexto
→ `allowed_evidence_ids`
→ `/api/v1/rag/evidence/search`
→ fragmentos autorizados
→ agente
→ guardrail
→ respuesta

## Regla de seguridad

RAG recupera; no autoriza.

La autorización pertenece a la política de contexto. El endpoint de evidencia
recibe `allowed_evidence_ids` ya calculados por el componente de acceso por rol.
