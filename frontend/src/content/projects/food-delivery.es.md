# Observabilidad de una aplicación de domicilios

Construí un pipeline de datos en AWS basado en eventos para monitorear una aplicación simulada de domicilios.

## Ingesta y almacenamiento

API Gateway recibió eventos JSON de la aplicación. AWS Lambda transformó los datos y los guardó en formato Parquet en un lago de datos de tres capas con tres buckets de S3.

## Análisis y despliegue

Amazon Athena consultó el lago de datos y un panel de Grafana alojado en Amazon EC2 mostró los resultados. Usé Terraform para definir la infraestructura y GitHub Actions para automatizar el despliegue.
