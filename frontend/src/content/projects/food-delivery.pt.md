# Observabilidade de um aplicativo de entrega de comida

Criei um pipeline de dados na AWS orientado a eventos para monitorar um aplicativo simulado de entrega de comida.

## Ingestão e armazenamento

O API Gateway recebeu eventos JSON do aplicativo. O AWS Lambda transformou os dados e os gravou em Parquet em um data lake de três camadas com três buckets do S3.

## Análise e implantação

O Amazon Athena consultou o data lake e um painel do Grafana hospedado no Amazon EC2 exibiu os resultados. Usei o Terraform para definir a infraestrutura e o GitHub Actions para automatizar a implantação.
