# RAG de casos clínicos

Este paquete recupera evidencia de los JSON del repositorio. No formula
diagnósticos ni decide qué datos revelar: el motor de reglas debe habilitar los
`evidence_id` de `on_request` y entregarlos en `allowed_evidence_ids`.

## Construir el índice

Instala primero los requisitos del repositorio y el codificador CPU:

```powershell
python -m pip install -r requirements.txt -r requirements-rag.txt
```

El comando valida los casos, aplica la compuerta de estado, protege los campos
protegidos, calcula embeddings con `intfloat/multilingual-e5-small` y guarda un
índice local reconstruible:

```powershell
python -m rag.build
```

Por defecto solo se indexan los casos `curado` de `data/cases/`. Para probar
CIR-001 junto con los datos curados, incluye explícitamente el archivo borrador:

```powershell
python -m rag.build --case CIR-001.json --include-status borrador
```

El índice y el JSONL de trazabilidad quedan bajo `.rag/` (excluidos de Git).
El archivo de índice contiene evidencia `on_request`; debe tratarse como dato
clínico restringido y no distribuirse como catálogo público. El prefiltrado del
retriever impide devolver esa evidencia salvo que el motor pase su
`evidence_id` en `allowed_evidence_ids`.

## Consultar

```python
from pathlib import Path
from rag.indexer import RAGIndex

retriever = RAGIndex.load(Path(".rag/index.json"), agent="medico_asistente")
results = retriever.search(
    "¿Qué dijo el paciente sobre su respiración?",
    case_id="CARD-001",
    allowed_evidence_ids=[],  # Sin evidencia desbloqueada: solo campos públicos.
    top_k=3,
)
```

`search` exige `case_id`. `search_cases` exige una `specialty` válida y solo
considera títulos y chunks públicos. Ambos aceptan `top_k` y `min_score`, aplican
los filtros antes del ranking y escriben una línea JSONL por llamada. Los
resultados incluyen `evidence_id` cuando el dato procede de un elemento del
esquema; el perfil y el título de catálogo usan identificadores sintéticos y
por eso devuelven `evidence_id: null`.

## Política y validación

- La lista blanca de texto está centralizada en `rag/policy.py`. Alias, códigos
  clínicos, `asset`, campos desconocidos y todo `protected.*` no se embeben.
- La validación estructural usa `CaseSchemaValidator` y el
  `schemas/caso.schema.json` del repositorio. El build también comprueba la
  serie 1.x.x y que todos los `evidence_id` sigan el prefijo del caso.
- El repositorio no contiene `validar_caso.py` ni un validador de reglas
  cruzadas E02-E13. Siguiendo el plan, este RAG no duplica esas reglas; deben
  integrarse cuando el validador oficial esté disponible. Por ello, superar el
  build actual no sustituye la validación clínica/de dominio.
- Los términos protegidos se comparan sin tildes y sin distinguir mayúsculas.
  Una coincidencia exacta aborta todo el build; raíces compartidas, como
  «apéndice»/«apendicitis» en CIR-001, generan advertencia para revisión manual.
- `allergies_recorded: false` no genera chunk público de alergias. Una alergia
  incluida en `on_request` sigue sujeta a `allowed_evidence_ids`.

## Datos y límites de evaluación

`data/cases/CARD-001.json` está curado y es el único caso publicable existente.
El [CIR-001.json](../../CIR-001.json) de la raíz está en borrador y pendiente de
revisión clínica. El modo `--include-status borrador` es únicamente para
desarrollo; no debe usarse con estudiantes.

Se usa similitud coseno sobre embeddings normalizados y se ordena por score
descendente, `evidence_id` y `chunk_id` para desempatar. `min_score=0.35` es un
umbral provisional: falta un gold set de 30-40 consultas y evidencia suficiente
para calibrarlo o reportar Recall@k, MRR y latencia p50. Las pruebas automáticas
verifican aislamiento, lista blanca, guard, filtros, determinismo, hash y log,
pero no equivalen a validación clínica ni a métricas de calidad representativas.

## Pruebas

Con el entorno del proyecto y sus dependencias de desarrollo instaladas:

```powershell
python -m pytest -q
```

`tests/test_rag.py` usa un codificador determinista de prueba, de modo que las
pruebas no descargan el modelo ni requieren conexión a Hugging Face. Para
comprobar la integración real del modelo, ejecuta el build documentado arriba;
la primera ejecución descarga sus pesos. Se recomienda guardar por separado la
salida del build, `pytest` y la fecha/versiones usadas para el informe.

El índice local usa puntuación coseno en Python, suficiente para el corpus
pequeño previsto en el plan. El identificador del modelo y la versión fijada de
`sentence-transformers` se escriben en el registro; para reproducibilidad
bit-a-bit entre máquinas también se debe fijar la revisión concreta del modelo
de Hugging Face en el despliegue.
