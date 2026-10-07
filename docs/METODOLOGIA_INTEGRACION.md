# Metodología de desarrollo — Integración incremental orientada a riesgos

La integración de EN-002 con RAG se realiza mediante iteraciones pequeñas y verificables.

## Iteración 0 — Baseline
- Mantener operativo EN-002.
- Ejecutar pruebas existentes del repositorio y API.
- No cambiar el contrato `caso.schema.json`.

## Iteración 1 — Integración RAG
- Reutilizar el módulo `rag/` sin mezclarlo con la lógica del repositorio.
- Exponer una capa FastAPI en `app/rag_router.py`.
- Mantener separación entre búsqueda multi-caso y recuperación dentro del caso activo.
- Validar que `protected` no forme parte del índice conversacional.

## Iteración 2 — Orquestación
- Implementar StateGraph.
- Estado mínimo: `session_id`, `case_id`, fase, agente, evidencias reveladas.
- El orquestador no accede indiscriminadamente al caso completo.

## Iteración 3 — Política de contexto
- Calcular `allowed_evidence_ids`.
- Aplicar `reveal_policy`.
- Hacer recuperación RAG dentro del `case_id` activo.
- Registrar toda evidencia recuperada.

## Iteración 4 — Agentes y guardrails
- Médico asistente.
- Paciente.
- Laboratorio.
- Radiología.
- Especialista.
- Validación de salida y fuga diagnóstica.

## Iteración 5 — Evaluación e integración frontend
- Motor de reglas.
- Evaluación del proceso clínico.
- Reporte final.
- Voz y avatares.

Cada iteración debe cerrar con compilación, pruebas automatizadas y evidencia de ejecución.
