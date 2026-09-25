# MySqlAutoBkps 🗄️⚡

> **Sistema profesional de respaldo automatizado para MySQL y MariaDB con interfaz de escritorio moderna, alta velocidad, respaldos completos e incrementales, y compatibilidad garantizada al 100% con phpMyAdmin.**

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python)](https://www.python.org/)
[![UI Framework](https://img.shields.io/badge/UI-CustomTkinter-2563EB)](https://github.com/TomSchimansky/CustomTkinter)
[![Security](https://img.shields.io/badge/Security-AES--Fernet%20Encrypted-10B981)](#-seguridad-y-gestión-de-credenciales)
[![Database](https://img.shields.io/badge/Compatibility-phpMyAdmin%20%7C%20MySQL%20%7C%20MariaDB-F59E0B?logo=mysql)](https://www.phpmyadmin.net/)
[![License](https://img.shields.io/badge/License-MIT-gray.svg)](LICENSE)

---

## 📋 Tabla de Contenidos
- [Características Principales](#-características-principales)
- [Arquitectura del Software](#-arquitectura-del-software)
- [Seguridad y Gestión de Credenciales](#-seguridad-y-gestión-de-credenciales)
- [Compatibilidad 100% con phpMyAdmin](#-compatibilidad-100-con-phpmyadmin)
- [Respaldos Autoincrementales](#-respaldos-autoincrementales)
- [Requisitos e Instalación](#-requisitos-e-instalación)
- [Guía de Uso](#-guía-de-uso)
- [Guía de Restauración en phpMyAdmin](#-guía-de-restauración-en-phpmyadmin)
- [Estructura del Proyecto](#-estructura-del-proyecto)

---

## ✨ Características Principales

- **100% Autónomo (Sin requerir MySQL instalado en tu PC/laptop)**: Incluye un **Motor Nativo en Python Puro** que extrae el 100% de la base de datos (Estructuras, Datos, Vistas, Procedimientos, Triggers y Eventos) directamente por protocolo de red, garantizando compatibilidad absoluta con cualquier versión de MySQL (5.0, 5.5, 5.6, 5.7, 8.0, 8.4, 9.0+) y MariaDB sin requerir `mysqldump` ni MySQL local.
- **Agrupación Inteligente Servidor-Bases de Datos**: Agrupa múltiples bases de datos bajo cada servidor configurado (Host, Puerto, Usuario, SSL y notas).
- **Importación Directa desde MySQL Workbench**: Detecta automáticamente tu archivo `connections.xml` de Workbench, listando tus conexiones configuradas para agregarlas con 1 clic.
- **Auto-descubrimiento en 1 Clic**: Consulta el servidor mediante `SHOW DATABASES` y permite importar todas las bases de datos con casillas de selección sin escribirlas a mano.
- **Respaldos Full e Incrementales**: Genera copias completas o deltas incrementales enlazados mediante manifiestos forenses (`manifests.json`).
- **Compresión en Streaming (`.sql.gz`)**: Comprime al vuelo sin saturar la RAM y calcula el hash de integridad SHA-256 en una sola pasada de I/O.
- **Seguridad Cero Contraseñas en Claro**: Cifrado local con **Fernet (AES-128-CBC + HMAC-SHA256)** y paso seguro de credenciales mediante `--defaults-extra-file` (nunca expone contraseñas en la lista de procesos de Windows/Linux).
- **Auto-inicialización Silenciosa**: Si descargas o clonas el proyecto sin archivos de configuración ni claves, la aplicación genera silenciosamente la clave maestra local (`config/.key`) y las configuraciones base sin interrumpir al usuario.
- **Planificador en Segundo Plano (APScheduler)**: Automatiza respaldos por intervalos (horas/días) o expresiones cron sin congelar la ventana.
- **Políticas de Retención Automática**: Depura automáticamente copias antiguas según antigüedad en días o número máximo de versiones por base de datos, protegiendo cadenas incrementales activas.
- **Consola de Operaciones en Vivo**: Monitoriza la actividad en tiempo real con colores diferenciados por nivel (Éxito, Información, Advertencia, Error).

---

## 🏛️ Arquitectura del Software

El sistema sigue una **Arquitectura en Capas Limpia (Clean Layered Architecture)** para garantizar modularidad, legibilidad y alta mantenibilidad:

```
+-------------------------------------------------------------------+
|                           CAPA DE UI                              |
|   (CustomTkinter: Dashboard, Programador, Historial, Ajustes)     |
+-------------------------------------------------------------------+
                                  │
                                  ▼
+-------------------------------------------------------------------+
|                        CAPA DE SERVICIOS                          |
|  - BackupService (Orquestador Full & Incr)                        |
|  - SchedulerService (APScheduler en background)                   |
|  - ConnectionService (Prueba y Auto-descubrimiento)               |
|  - RetentionService (Depuración inteligente)                      |
+-------------------------------------------------------------------+
             │                                          │
             ▼                                          ▼
+-------------------------+             +---------------------------+
|     CAPA DE MOTORES     |             |      MODELOS & CORE       |
| - DumpEngine (mysqldump)|             | - ServerConfig & DBConfig |
| - IncrementalEngine     |             | - BackupManifest (Forensic|
| - StreamCompressor (Gz) |             | - SecretManager (AES)     |
| - BinaryDetector (Auto) |             | - ConfigManager (Atómico) |
+-------------------------+             +---------------------------+
```

---

## 🛡️ Seguridad y Gestión de Credenciales

1. **Auto-inicialización Silenciosa y Segura**:
   - Al iniciar la aplicación por primera vez (o tras un `git clone`), si el directorio `config/` o el archivo `config/.key` no existen, se genera automáticamente una clave criptográfica de 32 bytes con permisos restringidos.
   - No se muestran cuadros de diálogo molestos ni errores de archivos faltantes.
2. **Cero Texto Plano en Disco y Memoria**:
   - Todas las contraseñas se almacenan cifradas con Fernet (`servers.enc.json`).
3. **Exclusión Estricta en Git (`.gitignore`)**:
   - Las claves maestras (`.key`), configuraciones con credenciales (`*.enc.json`), volcados generados (`*.sql`, `*.sql.gz`) y logs (`*.log`) están rigurosamente excluidos del control de versiones.
4. **Protección en la Tabla de Procesos**:
   - Las herramientas de volcado (`mysqldump`) no reciben contraseñas en la línea de comandos (`--password=...`), sino a través de un archivo de directivas temporales con permisos estrictos que se destruye inmediatamente tras el volcado.

---

## 🌐 Compatibilidad 100% con phpMyAdmin

Para garantizar que cualquier archivo `.sql` o `.sql.gz` generado por **MySqlAutoBkps** pueda ser importado limpiamente en **cualquier versión de phpMyAdmin** (desde versiones antiguas de cPanel hasta las más recientes en Docker o XAMPP):

| Parámetro | Propósito en phpMyAdmin |
|---|---|
| `--single-transaction` | Asegura consistencia ACID en tablas InnoDB sin bloquear lecturas de la base de datos. |
| `--quick` | Transmite los datos fila por fila evitando el consumo masivo de memoria RAM en bases de datos gigantes. |
| `--routines --triggers --events` | Respalda el 100% de la lógica de negocio (procedimientos, funciones, disparadores y eventos). |
| `--add-drop-table` | Añade `DROP TABLE IF EXISTS` para permitir reimportaciones limpias en phpMyAdmin sin errores de colisión. |
| `--add-locks` y `--disable-keys` | Desactiva temporalmente índices y bloquea tablas durante el volcado para una importación 10 veces más rápida. |
| `--hex-blob` | Vuelca campos binarios e imágenes en formato hexadecimal, impidiendo corrupción de caracteres en phpMyAdmin. |
| `--default-character-set=utf8mb4` | Soporte nativo universal para todos los idiomas, emojis y caracteres especiales. |
| `--set-gtid-purged=OFF` | Evita fallos de privilegios `SUPER` / `SYSTEM_VARIABLES_ADMIN` habituales en hostings compartidos. |

---

## 🔄 Respaldos Autoincrementales

MySqlAutoBkps implementa una cadena de respaldo estructurada:
1. **Respaldo Base (FULL)**: Crea el ancla de la cadena y captura el estado global junto con las coordenadas de log binario (`binlog_file` y `binlog_position`).
2. **Respaldo Incremental (INCR)**:
   - Extrae únicamente las transacciones ejecutadas desde el punto anterior mediante `mysqlbinlog` o genera deltas consistentes compatibles con SQL estándar.
   - Cada respaldo incremental queda enlazado a su `base_backup_id` y recibe un número secuencial en la cadena (`chain_index`).
   - El asistente de restauración indica el orden exacto de importación: `Full Base` ➔ `Incr #1` ➔ `Incr #2`...

---

## 🚀 Requisitos e Instalación

### Requisitos Previos
- **Python**: Versión 3.10, 3.11 o 3.12 instalada.
- **MySQL / MariaDB**: Instalación local (XAMPP, Laragon, WampServer, Docker o MySQL Server) o conexión remota accesible por red.

### Instalación Rápida

1. **Clonar el repositorio**:
   ```bash
   git clone https://github.com/yarkosg/MySqlAutoBkps.git
   cd MySqlAutoBkps
   ```

2. **Instalar dependencias**:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Ejecutar la aplicación**:
   ```bash
   python main.py
   ```
   *(Los archivos `config/.key`, `config/servers.enc.json` y `config/settings.json` se crearán automáticamente en el primer arranque).*

---

## 🖥️ Guía de Uso

1. **Añadir Servidor**:
   - En la vista **Panel de Control**, haz clic en `+ Añadir Servidor`.
   - Ingresa Host, Puerto, Usuario y Contraseña.
   - Haz clic en `🔌 Probar Conexión` para verificar conectividad.
   - Haz clic en `🔍 Auto-descubrir BDs` para cargar automáticamente todas las bases de datos del servidor y marca las que desees respaldar.
   - Guarda el servidor.
2. **Ejecutar Respaldos**:
   - **Manual**: Haz clic en `Full` o `Incr.` junto a cada base de datos, o usa `Respaldar Servidor` / `Respaldar Todo`.
   - Observa la barra de progreso y los registros en la **Consola de Operaciones en Vivo**.
3. **Programar Tareas Automáticas**:
   - Dirígete a la pestaña **⏰ Programador**.
   - Haz clic en `+ Programar Tarea`, define la frecuencia (ej. Diario a las 02:00 o cada N horas), el tipo (Full o Incremental) y actívala.
   - El motor en segundo plano ejecutará los respaldos de forma desatendida.
4. **Verificar Integridad**:
   - En la pestaña **📜 Historial & Restaurar**, haz clic en `📖 phpMyAdmin Guía` sobre cualquier respaldo para consultar las instrucciones y validar su hash SHA-256 contra manipulaciones.

---

## 📖 Guía de Restauración en phpMyAdmin

1. Abre tu navegador e ingresa a **phpMyAdmin**.
2. En el panel izquierdo, selecciona la base de datos de destino (o crea una nueva vacía con cotejamiento `utf8mb4_general_ci`).
3. Haz clic en la pestaña superior **Importar** (*Import*).
4. En **Seleccionar archivo**, elige tu archivo de respaldo:
   - Si es comprimido (`.sql.gz`), phpMyAdmin lo descomprime y procesa automáticamente sin pasos adicionales.
5. Si restauras una **cadena incremental**:
   - Importa primero el archivo `dump_..._FULL.sql.gz`.
   - Luego importa consecutivamente los archivos `incr_..._chain1.sql.gz`, `incr_..._chain2.sql.gz`, etc.
6. Haz clic en **Continuar** (*Import*).

---

## 📁 Estructura del Proyecto

```
MySqlAutoBkps/
│
├── config/                          # Configuración local cifrada (Ignorado en Git)
│   ├── .key                         # Clave de cifrado Fernet AES (Auto-generada)
│   ├── servers.enc.json             # Servidores y credenciales cifradas
│   ├── settings.json                # Preferencias globales y rutas
│   └── jobs.json                    # Tareas programadas
│
├── src/
│   ├── core/                        # Núcleo del sistema
│   │   ├── config.py                # Gestor de configuración atómica
│   │   ├── security.py              # Criptografía Fernet AES
│   │   ├── logger.py                # Logger multicanal (UI + Archivo rotativo)
│   │   └── exceptions.py            # Jerarquía de excepciones tipadas
│   │
│   ├── models/                      # Modelos de datos
│   │   ├── database.py              # DatabaseConfig
│   │   ├── server.py                # ServerConfig
│   │   ├── manifest.py              # BackupManifest & BackupType
│   │   └── backup_job.py            # BackupJob
│   │
│   ├── engine/                      # Motores de bajo nivel
│   │   ├── detector.py              # Detección inteligente de mysqldump / mysqlbinlog
│   │   ├── compressor.py            # Compresión streaming Gzip con SHA-256 en vivo
│   │   ├── dump_engine.py           # Volcado con banderas completas para phpMyAdmin
│   │   └── incremental_engine.py    # Motor de respaldos incrementales y deltas
│   │
│   ├── services/                    # Lógica de negocio
│   │   ├── connection_service.py    # Validación de conexión y SHOW DATABASES
│   │   ├── backup_service.py        # Orquestación de copias y manifiestos
│   │   ├── retention_service.py     # Depuración automática por días/versiones
│   │   └── scheduler_service.py     # Planificador en background con APScheduler
│   │
│   └── ui/                          # Capa de presentación (CustomTkinter)
│       ├── app.py                   # Ventana principal y navegación por sidebar
│       ├── theme.py                 # Paleta estética moderna y tipografías
│       ├── components/              # Componentes visuales reutilizables
│       ├── dialogs/                 # Diálogos modales (Servidor, Tarea, Restauración)
│       └── views/                   # Vistas principales (Dashboard, Scheduler, History, Settings)
│
├── backups/                         # Carpeta predeterminada de respaldos (Ignorado en Git)
├── logs/                            # Logs de ejecución rotativos (Ignorado en Git)
├── tests/                           # Suite de pruebas automatizadas
│   └── test_mysql_autobkps.py
├── main.py                          # Punto de entrada de la aplicación
├── requirements.txt                 # Dependencias oficiales
├── .gitignore                       # Exclusión estricta de seguridad
└── README.md                        # Documentación técnica completa
```

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo `LICENSE` para mayores detalles.
