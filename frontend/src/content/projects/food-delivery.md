# SendFast Analytics: delivery data on AWS

I built an AWS analytics platform for a simulated food delivery business. SendFast connects an authenticated ordering interface to transactional storage, a scheduled data lake pipeline, and SQL-backed dashboards, with Terraform and GitHub Actions managing infrastructure and delivery.

## Secure web access and order ingestion

The React, TypeScript, and Vite frontend is delivered through CloudFront from a private S3 bucket using Origin Access Control. AWS WAF protects the CloudFront distribution, while Cognito authenticates users and an API Gateway JWT authorizer protects the ingestion API.

A Python Lambda validates incoming order data, normalizes timestamps to UTC, writes the order to DynamoDB, and saves a JSON copy in the S3 Raw layer. Orders include delivery time, amount, zone, status, and payment method, providing the inputs for business reporting.

## Scheduled ETL and a queryable data lake

EventBridge schedules a separate ETL Lambda using pandas and AWS SDK for pandas. The job tracks a processing checkpoint, identifies affected days, normalizes column types, and deduplicates records by order ID before writing Parquet to the S3 Stage layer.

The Parquet dataset is partitioned by year, month, and day and registered in the Glue Data Catalog. Changed daily partitions are overwritten, and the checkpoint advances after output and catalog updates succeed. Athena queries that dataset and stores query results in a separate S3 bucket.

## Grafana and operational access

Grafana runs in Docker on EC2 with the Athena datasource provisioned during instance startup. Its administrator credentials are retrieved from AWS Secrets Manager through the instance profile. Grafana access is restricted to configured CIDR ranges, and SSH is disabled by default.

This separates the public ordering interface, ingestion API, analytical storage, and dashboard access into distinct components.

## Infrastructure and CI/CD

Reusable Terraform modules define the web delivery, WAF, Cognito, API Gateway, Lambda functions, DynamoDB, S3, EventBridge, Glue, Athena, and Grafana resources.

GitHub Actions checks Terraform formatting and validation, runs Lambda linting and handler tests, and checks TypeScript and the web build. Deployment uses AWS OIDC credentials, applies Terraform, and exports infrastructure outputs to generate the frontend's production configuration. The pipeline then builds the web application, publishes it to S3, and invalidates CloudFront.

The project demonstrates the complete path from an application event to analytical reporting, including validation, incremental processing, access control, and automated deployment.
