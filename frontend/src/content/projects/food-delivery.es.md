# SendFast Analytics: datos de domicilios en AWS

Construí una plataforma de analítica en AWS para un negocio simulado de domicilios. SendFast conecta una interfaz de pedidos autenticada con almacenamiento transaccional, un pipeline programado para el lago de datos y tableros basados en consultas SQL, con Terraform y GitHub Actions para gestionar infraestructura y despliegue.

## Acceso web seguro e ingesta de pedidos

El frontend de React, TypeScript y Vite se entrega mediante CloudFront desde un bucket S3 privado con Origin Access Control. AWS WAF protege la distribución de CloudFront, mientras Cognito autentica a los usuarios y un autorizador JWT de API Gateway protege la API de ingesta.

Una Lambda en Python valida los pedidos, normaliza sus fechas a UTC, escribe cada pedido en DynamoDB y guarda una copia en JSON en la capa Raw de S3. Los pedidos incluyen tiempo de entrega, monto, zona, estado y método de pago, que sirven como entradas para los informes del negocio.

## ETL programado y un lago de datos consultable

EventBridge programa una Lambda ETL independiente que utiliza pandas y AWS SDK for pandas. El trabajo mantiene un punto de control, identifica los días afectados, normaliza los tipos de las columnas y elimina duplicados por identificador de pedido antes de escribir Parquet en la capa Stage de S3.

El conjunto de datos Parquet se particiona por año, mes y día y se registra en Glue Data Catalog. Las particiones diarias modificadas se sobrescriben y el punto de control avanza después de completar la escritura y las actualizaciones del catálogo. Athena consulta ese conjunto de datos y almacena los resultados de las consultas en otro bucket S3.

## Grafana y acceso operativo

Grafana se ejecuta en Docker sobre EC2, con el datasource de Athena configurado durante el arranque de la instancia. Las credenciales de administración se recuperan desde AWS Secrets Manager mediante el perfil de instancia. El acceso a Grafana se restringe a los rangos CIDR configurados y SSH está deshabilitado por defecto.

Así, la interfaz pública de pedidos, la API de ingesta, el almacenamiento analítico y el acceso al tablero quedan separados en componentes distintos.

## Infraestructura y CI/CD

Módulos reutilizables de Terraform definen la entrega web, WAF, Cognito, API Gateway, las funciones Lambda, DynamoDB, S3, EventBridge, Glue, Athena y los recursos de Grafana.

GitHub Actions comprueba el formato y la validez de Terraform, ejecuta linting y pruebas de los handlers de Lambda, y verifica TypeScript y la compilación web. El despliegue utiliza credenciales AWS por OIDC, aplica Terraform y exporta sus outputs para generar la configuración de producción del frontend. Después, el pipeline compila la aplicación, la publica en S3 e invalida CloudFront.

El proyecto muestra el recorrido completo desde un evento de aplicación hasta un informe analítico, incluyendo validación, procesamiento incremental, control de acceso y despliegue automatizado.
