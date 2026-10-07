# Pruebas del RAG de casos clínicos

Sigue estos pasos desde la raíz del repositorio en PowerShell.

## 1. Crear y activar el entorno virtual

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación del entorno, permite scripts para la sesión
actual y vuelve a activarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

## 2. Instalar dependencias

```powershell
python -m pip install -r requirements.txt -r requirements-rag.txt
```

## 3. Ejecutar las pruebas del RAG

```powershell
python -m pytest -q tests/test_rag.py
```

Las pruebas usan un codificador determinista de prueba, por lo que no descargan
los pesos del modelo E5 ni requieren conexión a Hugging Face.

## Integración FastAPI + RAG

La aplicación conserva los endpoints EN-002 y añade:

| Método | Ruta | Finalidad |
|---|---|---|
| GET | `/api/v1/rag/health` | Estado del índice RAG |
| POST | `/api/v1/rag/cases/search` | Recuperar casos candidatos por especialidad + similitud |
| POST | `/api/v1/rag/evidence/search` | Recuperar evidencia del `case_id` activo |
| POST | `/api/v1/rag/reload` | Recargar el índice persistido |

### Preparar el entorno RAG

```powershell
pip install -r requirements.txt
pip install -r requirements-rag.txt
python -m rag.build
uvicorn app.main:app --reload
```

### Metodología

Ver:

- `docs/METODOLOGIA_INTEGRACION.md`
- `docs/ARQUITECTURA_INTEGRADA.md`

El RAG no reemplaza la política de acceso. Para una sesión, EN-004 deberá calcular
`allowed_evidence_ids` y luego invocar `/api/v1/rag/evidence/search`.
