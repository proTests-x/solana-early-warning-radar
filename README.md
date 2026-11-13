# Memecoin Early-Warning Radar

Radar local y conservador para Solana. Descubre tokens con DEX Screener, calcula features y
scores en Python, consulta seguridad/social cuando hay credenciales, usa Qwen en Ollama como
capa explicativa y puede enviar alertas a Telegram. Nunca compra ni vende.

## Inicio rápido

Requiere Python 3.10+ (3.11+ recomendado) y Ollama en ejecución.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item config\config.example.json config\config.json
Copy-Item config\secrets.example.json config\secrets.json
python scripts\test_ollama.py
python app.py --once
```

El modelo configurado inicialmente es `qwen3.5:9b`. Cámbialo en
`config/config.json` si el tag instalado es distinto.

Para ejecución continua:

```powershell
python app.py
```

Para analizar un mint concreto:

```powershell
python scripts\analyze_token.py MINT
```

## Credenciales opcionales

Edita `config/secrets.json`. Las claves vacías desactivan Telegram, X y LunarCrush sin detener
el radar. GoPlus se intenta sin token y cualquier fallo queda registrado como seguridad
desconocida; nunca como token seguro.

Los datos se guardan en `data/`: estado pequeño en JSON y snapshots/historiales append-only
en JSONL. `BUY_CANDIDATE` es una señal heurística para revisión humana, no una predicción ni
una garantía de rentabilidad.

## Alertas de riesgo

- `RUG_WATCH`: actividad de mercado suficiente junto con riesgo alto. Es una alerta de
  vigilancia y **no** una recomendación de compra.
- `EXIT_WARNING`: un token ya vigilado muestra deterioro nuevo, como caída de liquidez o
  precio, buy/sell por debajo del límite, salto del Risk Score o aceleración de ventas.

Los umbrales y cooldowns están en `alerts.rug_watch` y `alerts.exit_warnings` dentro de
`config/config.json`. Ninguna alerta garantiza que todavía exista liquidez o que una venta
pueda ejecutarse al precio observado.

Los tokens que ya llegan colapsados se descartan sin alerta de oportunidad mediante
`alerts.collapsed_tokens` (caídas extremas de precio, liquidez o dominio masivo de ventas).
Si el token ya estaba vigilado, recibe una última `EXIT_WARNING` y queda marcado como colapso
terminal para impedir que un rebote posterior vuelva a presentarlo como candidato.

Cuando Ollama falla, supera el timeout o devuelve JSON que no cumple el esquema, el radar
repite el análisis según `ollama.max_attempts` y `ollama.retry_delay_seconds`.

## Pruebas

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Publicación de código

Esta copia no incluye credenciales, historial de alertas ni listas de seguimiento personales. Las integraciones externas requieren configuración propia. Es una herramienta informativa experimental, no asesoramiento financiero ni un sistema de ejecución de operaciones.
