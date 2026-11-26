# Qair: Bogotá air quality alerts

I contributed to a university project that turns Bogotá PM2.5 measurements into station-level air quality alerts. Qair combines automated data collection, a traceable Python calculation engine, and an interactive map for exploring results and downloading the calculations behind them.

## From SISAIRE reports to station alerts

Users can upload CSV or Excel measurements, or request reports from SISAIRE through a Playwright browser automation workflow. The backend consolidates station reports and uses a CAR/SISAIRE catalog to fill in station coordinates.

The pandas engine calculates a 24-hour rolling mean for hourly measurements, requiring 18 valid readings by default. Daily reports that already contain an aggregated average use that value directly. Candidate alert levels are evaluated over the next 48 readings, with a persistence criterion above 75%. Each run produces calculation records in CSV and Excel, a station summary, and GeoJSON for the map.

These are the rules implemented by the project; the dashboard presents their results with the underlying calculation records available for review.

## An API with persistent calculation sessions

FastAPI exposes manual calculation and automatic sampling endpoints. Background jobs report their status, progress, current step, events, and errors, allowing the frontend to follow a run and revisit earlier results.

SQLAlchemy stores job history in SQLite for local development or PostgreSQL when a database connection is configured. The backend also provides station catalogs, health checks, and endpoints for downloading generated files.

## React dashboard and mapping

The frontend uses React, Vite, Tailwind CSS, and Leaflet. It brings together file uploads, station and date filters for sampling, progress reporting, a session history panel, and the results map. GeoJSON connects the Python outputs to the station markers and their calculated status.

## Containerized deployment on AWS

The Terraform stack defines a private S3 frontend behind CloudFront with Origin Access Control. Requests to `/api/*` are forwarded through an Application Load Balancer to FastAPI running on ECS Fargate.

ECR stores the backend image, RDS PostgreSQL persists calculation sessions, and encrypted EFS retains generated files. ECS receives the database connection through Secrets Manager and sends application logs to CloudWatch. Docker Compose provides a local API and PostgreSQL environment.

## Validation and delivery

GitHub Actions runs Ruff and Pytest for the Python backend and builds the React application from its npm lockfile. Separate repository scripts publish the backend image to ECR and deploy the frontend to S3 with a CloudFront invalidation.

The project connects data ingestion, reproducible calculations, API design, GIS visualization, and infrastructure as code in a single workflow.
