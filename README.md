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
