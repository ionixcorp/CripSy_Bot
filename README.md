# ♻️ PocketOption POC Bot (BinaryOptionsToolsV2 Powered)

Este es un **bot táctico de señales y ejecución automática** desarrollado para operar en **Pocket Option**, utilizando como núcleo la librería oficial no publicada `BinaryOptionsToolsV2`.
---

## 🚀 Características principales

- ✅ Conexión en tiempo real a Pocket Option usando **SSID**
- ✅ Análisis técnico basado en volumen y perfil horizontal (POC)
- ✅ Estrategia del **rechazo al POC** con confirmación por vela
- ✅ Arquitectura 100% asíncrona (`asyncio`)
- ✅ Reconstrucción de velas personalizada por timeframe
- ✅ Ejecución real de órdenes con `buy` y `sell` sobre la API oficial
- ✅ Sistema de logs claros y visuales por ciclos de operación

---

## 🧠 ¿Qué es BinaryOptionsToolsV2?

`BinaryOptionsToolsV2` es una librería avanzada para interactuar con Pocket Option. Ofrece:

- Conexión WebSocket nativa
- Acceso a balance, payout, historial
- Suscripción en tiempo real a símbolos y velas
- Envío de operaciones con `buy()` / `sell()` y validación de resultados
- Soporte para raw-orders y validación custom con `Validator`

> Esta librería, se instala desde código fuente. O desde PyPI.

Pocket-Option API: https://github.com/ChipaDevTeam/BinaryOptionsTools-v2

## 📂 Estructura del proyecto

```bash
PocketOptionBot/
├── core/
│   ├── __init__.py 
│   ├── connection.py           # Wrapper oficial de conexión y ejecución
│   └── settings.py             # Configuración general y acceso a .env
├── modules/
│   ├── __init__.py 
│   ├── executor.py             # Manejo de ejecución de operaciones
│   ├── collector.py            # Recolector de ticks en tiempo real
│   └── constructor.py          # Reconstrucción de velas + análisis POC
├── strategies/
│   ├── __init__.py 
│   └── strategy_base.py        # Estrategia #1: Rechazo al POC
├── main.py                     # Orquestador del sistema
├── requirements.txt
└── README.md