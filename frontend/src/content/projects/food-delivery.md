# Food delivery observability

I built an event-driven AWS data pipeline to monitor a simulated food delivery application.

## Ingestion and storage

API Gateway received JSON events from the application. AWS Lambda transformed the incoming payloads and wrote Parquet data into a three-tier data lake backed by three S3 buckets.

## Analytics and deployment

Amazon Athena queried the data lake, and a Grafana dashboard hosted on Amazon EC2 displayed the results. I used Terraform to define the infrastructure and GitHub Actions to automate deployment.
