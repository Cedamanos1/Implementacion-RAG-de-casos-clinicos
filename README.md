# EN-002 · Repositorio y API de Casos Clínicos

Implementación del habilitador EN-002 del **Paciente Virtual Adaptativo**.

## Qué cubre
- Valida cada JSON con `schemas/caso.schema.json`.
- Solo carga casos con `status = "curado"`.
- Lista especialidades disponibles.
- Selecciona un caso aleatorio por especialidad.
- Expone al frontend únicamente `public`.
- Expone un índice de `on_request` sin `text`, `value` ni `unit`.
- No existe endpoint público para `protected`.

> La liberación real de datos `on_request` corresponde a EN-004 (Política de Contexto y Recuperación Selectiva).

## Instalación
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Pruebas
```powershell
python -m pytest -q
```

## API
```powershell
uvicorn app.main:app --reload
```
Swagger: `http://127.0.0.1:8000/docs`

## RAG de recuperación de evidencia
Consulta [docs/rag/README.md](docs/rag/README.md) para instalar, construir y
consultar el índice local de evidencia clínica.

## Endpoints
- `GET /health`
- `GET /api/v1/repository/status`
- `POST /api/v1/repository/reload`
- `GET /api/v1/specialties`
- `GET /api/v1/cases`
- `POST /api/v1/cases/select`
- `GET /api/v1/cases/{case_id}/public`
- `GET /api/v1/cases/{case_id}/on-request-index`
