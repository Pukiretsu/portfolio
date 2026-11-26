# Qair: alertas de calidad del aire en Bogotá

Participé en un proyecto universitario que transforma mediciones de PM2.5 de Bogotá en alertas de calidad del aire por estación. Qair combina recopilación automatizada, un motor de cálculo trazable en Python y un mapa interactivo para explorar resultados y descargar los cálculos que los respaldan.

## De los reportes de SISAIRE a las alertas por estación

Los usuarios pueden cargar mediciones en CSV o Excel, o solicitar reportes de SISAIRE mediante un flujo de automatización del navegador con Playwright. El backend consolida los reportes y utiliza un catálogo CAR/SISAIRE para completar las coordenadas de las estaciones.

El motor de pandas calcula una media móvil de 24 horas para las mediciones horarias y exige 18 lecturas válidas por defecto. Cuando un reporte diario ya contiene un promedio agregado, utiliza ese valor directamente. Los niveles candidatos se evalúan durante las siguientes 48 lecturas, con un criterio de persistencia superior al 75 %. Cada ejecución genera registros de cálculo en CSV y Excel, un resumen por estación y un GeoJSON para el mapa.

Estas son las reglas implementadas por el proyecto; el tablero presenta sus resultados y permite consultar los registros de cálculo que los sustentan.

## Una API con sesiones de cálculo persistentes

FastAPI expone endpoints de cálculo manual y muestreo automático. Los trabajos en segundo plano informan su estado, progreso, paso actual, eventos y errores, de modo que el frontend puede seguir una ejecución y consultar resultados anteriores.

SQLAlchemy guarda el historial de trabajos en SQLite para desarrollo local o en PostgreSQL cuando se configura la conexión. El backend también ofrece catálogos de estaciones, comprobaciones de salud y endpoints para descargar los archivos generados.

## Tablero React y cartografía

El frontend utiliza React, Vite, Tailwind CSS y Leaflet. Reúne carga de archivos, filtros de estaciones y fechas para el muestreo, seguimiento del progreso, un panel de historial de sesiones y el mapa de resultados. GeoJSON conecta las salidas de Python con los marcadores de las estaciones y su estado calculado.

## Despliegue con contenedores en AWS

La infraestructura Terraform define un frontend en S3 privado detrás de CloudFront con Origin Access Control. Las solicitudes a `/api/*` pasan por un Application Load Balancer hacia FastAPI en ECS Fargate.

ECR almacena la imagen del backend, RDS PostgreSQL conserva las sesiones de cálculo y EFS cifrado mantiene los archivos generados. ECS recibe la conexión de base de datos desde Secrets Manager y envía los logs de la aplicación a CloudWatch. Docker Compose proporciona un entorno local para la API y PostgreSQL.

## Validación y entrega

GitHub Actions ejecuta Ruff y Pytest para el backend de Python y compila la aplicación React desde su lockfile de npm. Scripts separados publican la imagen del backend en ECR y despliegan el frontend en S3 con una invalidación de CloudFront.

El proyecto conecta ingesta de datos, cálculos reproducibles, diseño de API, visualización SIG e infraestructura como código en un mismo flujo.
