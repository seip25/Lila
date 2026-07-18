# About Lila

Lila is a  Python framework based on Starlette and Pydantic. Designed for developers seeking simplicity, flexibility, and robustness, it enables efficient and customizable Web or API application development. Its modular structure and support for advanced configurations make it suitable for both beginners and experienced developers.


# Acerca de  Lila (Español)

Lila es un framework  de Python basado en Starlette y Pydantic. Diseñado para desarrolladores que buscan simplicidad, flexibilidad y robustez, permite crear aplicaciones Web o APIs de manera eficiente y personalizable. Su estructura modular y soporte para configuraciones avanzadas lo hacen ideal tanto para principiantes como para desarrolladores experimentados.

# Learning Lila
https://seip25.github.io/Lila 

# Documentación de Lila
https://seip25.github.io/Lila


https://pypi.org/project/lila-framework/   
 

## Key Features

- **Simplicity**: Intuitive and minimalist design.
- **Flexibility**: Support for multiple databases (MySQL, PostgreSQL, SQLite) and adaptation to various environments.
- **Speed**: Built on Starlette, known for its high performance in asynchronous applications.
- **Robust Validation**: Uses Pydantic to ensure consistent data.
- **Editable and Configurable**: Ready to use but fully customizable.
- **Multi-language Support**: Integrated support for multilingual applications.
- **Compatibility**: Can be used with frameworks like Next.js, Remix, and others.
- **Easy Migrations**: Quick and straightforward database configuration.
- **Asynchronous Database**: Native async support for SQLite, MySQL, and PostgreSQL with automatic query deduplication to prevent event loop blocking.
- **Redis Cache & Sessions**: Fully asynchronous distributed session tracking and cache support with automatic local memory fallback.
- **Jinja2 and HTML Sessions**: Ready-to-use with dynamic templates and session handling, while remaining compatible with React, Angular, Vue, and other frontend frameworks.
- **Background Task Worker**: A hybrid queue mechanism for processing heavy background tasks via `lila-worker` or Starlette fallbacks.
- **Distributed WebSockets**: Scale WebSockets across multiple processes/nodes effortlessly using Redis Pub/Sub.
- **SQLAlchemy**: For the ORM or you can also use the connectors directly (mysql.connector, sqlite3, etc...)
- **JWT**: It comes integrated with helpers to generate tokens and the middleware already has a function that validates it.
- **Admin Panel**: Includes a built-in admin panel for easy management of your application's data and settings.
- **Robust Security**: Features IP blocking, URL filtering, and request sanitization to prevent malicious attacks and suspicious requests.
- **REST CRUD Generator**: Generate REST APIs with just a few lines of code. Includes field validations and middleware support.

---

## Características principales

- **Simplicidad**: Diseño intuitivo y minimalista.
- **Flexibilidad**: Soporte para múltiples bases de datos (MySQL, PostgreSQL, SQLite) y adaptación a diversos entornos.
- **Rapidez**: Basado en Starlette, conocido por su alto rendimiento en aplicaciones asíncronas.
- **Validación robusta**: Uso de Pydantic para garantizar datos consistentes.
- **Editable y configurable**: Todo está listo para usar, pero también es completamente personalizable.
- **Multi-idioma**: Soporte integrado para aplicaciones multilingües.
- **Compatibilidad**: Puede ser utilizado con frameworks como Next.js, Remix js, entre otros.
- **Migraciones sencillas**: Configuración rápida y fácil para bases de datos.
- **Base de Datos Asíncrona**: Soporte nativo asíncrono para SQLite, MySQL y PostgreSQL con deduplicación automática de consultas para evitar bloqueos del bucle de eventos.
- **Caché y Sesiones con Redis**: Soporte asíncrono para caché distribuido y manejo de sesiones en servidor Redis con fallback automático a memoria local.
- **Jinja2 y sesiones HTML**: Listo para usar con plantillas dinámicas y manejo de sesiones, pero compatible con React, Angular, Vue, entre otros frameworks frontend.
- **Worker de Tareas en Segundo Plano**: Mecanismo de cola híbrido para procesar tareas pesadas en segundo plano vía `lila-worker` o fallback local.
- **WebSockets Distribuidos**: Escala conexiones WebSocket entre múltiples procesos/nodos sin esfuerzo usando Redis Pub/Sub.
- **SQLAlchemy**: Para la ORM o también se puede utilizar los connectores directamente(mysql.connector,sqlite3,etc...)
- **JWT**: Viene integrado con helpers para generar token y en el middleware ya viene una función que válida el mismo.
- **Panel de Administración**: Incluye un panel de administración integrado para gestionar fácilmente los datos y configuraciones de tu aplicación.
- **Seguridad Robusta**: Cuenta con bloqueo de IPs, filtrado de URLs y sanitización de solicitudes para prevenir ataques maliciosos y solicitudes sospechosas.
- **Generador de APIs REST**: Genera APIs REST con solo unas pocas líneas de código. Incluye validaciones de campos y soporte para middlewares.


---

## CDN & Style Delivery
Lila features zero-dependency, compiled-free style delivery. The framework uses `asset('css/tailwind.css')` to automatically load Google Fonts (Outfit & Inter), Tailwind Play CDN, theme configuration, and the custom Lila design system components. Everything compiles in the browser instantly with full support for dark/light themes.

---

## CDN y Entrega de Estilos
Lila no requiere dependencias de Node.js o Vite para procesar el frontend. A través del helper `asset('css/tailwind.css')`, inyecta dinámicamente Google Fonts (Outfit e Inter), Tailwind Play CDN, configuraciones de tema y la capa de componentes CSS de Lila. Todo se procesa directamente en el navegador, soportando tema oscuro y claro nativamente.

---

## Installation (Instalación)
## Installation

### English

1. Install Lila Framework using pip:

```bash
   pip install lila-framework
    
```
2. Initialize your Lila project:
 ```bash
  lila-init
    
```
3. Run application:

```bash
   python app.py #Or python3 app.py
```

---

### Español

1. Instala Lila Framework usando pip:

```bash
   pip install lila-framework
    
```
2. Inicializa tu proyecto Lila:
 ```bash
  lila-init
    
```
3. Ejecutar aplicación:

```bash
   python app.py #Or python3 app.py
```
---

## Contributions (Contribuciones)

At this stage, all official modifications to the framework will be made only by the original author. However, any feedback or suggestions to improve the project are welcome.

Actualmente, todas las modificaciones oficiales al framework serán realizadas únicamente por el autor original. Sin embargo, se agradece cualquier comentario o sugerencia que pueda mejorar el proyecto.


[![Donar](https://img.shields.io/badge/Donar-PayPal-blue)](https://www.paypal.com/donate/?business=C65NYY5JGJZDS&no_recurring=0&item_name=Si+te+gusta+mi+trabajo%2C+puedes+apoyarme.%0ALas+donaciones+me+ayudan+a+dedicar+m%C3%A1s+tiempo+a+mejorar+este+proyecto&currency_code=USD)  

