# About Lila

Lila is a lightweight full-stack Python framework built on **Starlette**,
**Pydantic v2**, **SQLAlchemy 2.0 Async** and **Jinja2**. It is designed for
simple, fast deployments with 1–2 workers: SQLite WAL by default, an in-memory
LRU cache, optional Redis only when it is reachable, and a file-cache fallback.
Python **3.10+** is required.

- Typed routes, automatic JSON/HTML responses, Pydantic body validation.
- SPA navigation without a Node.js build step (`lila-client.js`).
- Async ActiveRecord models with schema sync (`lila migrate` adds missing columns).
- Sessions that never store passwords, CSRF for forms and JSON, Argon2id.
- Auth 2.0 scaffold (login, register, reset, profile, OAuth).
- Admin 2.0 with sanitized CRUD, CSV export, cache purge and real telemetry.
- AI helper (OpenAI/DeepSeek/Gemini) with PII masking.
- One-command desktop builds (`lila desktop build`).
- Built-in locales: English, Spanish, Portuguese and Simplified Chinese.

## Install

```bash
pip install lila-framework
lila init
lila dev
```

Optional extras: `redis`, `postgres`, `mysql`, `images`, `markdown`, `metrics`,
`optimize`, `desktop`.

## Documentation

https://seip25.github.io/Lila

# Acerca de Lila (Español)

Lila es un framework full-stack liviano de Python basado en **Starlette**,
**Pydantic v2**, **SQLAlchemy 2.0 Async** y **Jinja2**. Está pensado para
despliegues simples y rápidos con 1–2 workers: SQLite WAL por defecto, cache LRU
en memoria, Redis opcional solo si está disponible y fallback a cache en archivos.
Requiere **Python 3.10+**.

- Rutas tipadas, respuestas JSON/HTML automáticas y validación con Pydantic.
- Navegación SPA sin Node.js (`lila-client.js`).
- Modelos ActiveRecord async con sincronización de esquema (`lila migrate` agrega
  columnas faltantes).
- Sesiones que nunca guardan contraseñas, CSRF para formularios y JSON, Argon2id.
- Scaffold de Auth 2.0 (login, registro, reset, perfil, OAuth).
- Admin 2.0 con CRUD sanitizado, exportación CSV, purga de cache y telemetría real.
- Helper de IA (OpenAI/DeepSeek/Gemini) con enmascarado de PII.
- Compilación de escritorio en un comando (`lila desktop build`).
- Idiomas incluidos: inglés, español, portugués y chino simplificado.

## Instalación

```bash
pip install lila-framework
lila init
lila dev
```

Extras opcionales: `redis`, `postgres`, `mysql`, `images`, `markdown`, `metrics`,
`optimize`, `desktop`.

## Documentación

https://seip25.github.io/Lila

---

## Contributions (Contribuciones)

At this stage, all official modifications to the framework will be made only by
the original author. Feedback and suggestions are welcome.

Actualmente, todas las modificaciones oficiales al framework serán realizadas
únicamente por el autor original. Se agradecen comentarios y sugerencias.
