# Portfolio infrastructure

Requires Terraform >= 1.10, AWS credentials, and an existing Cloudflare zone for the root domain with working nameserver delegation. The API token needs Zone DNS Edit permission scoped to that zone.

```sh
cd infra
cp terraform.tfvars.example terraform.tfvars
# Set your domain, Cloudflare zone ID, and bucket region in terraform.tfvars.
# Export TF_VAR_cloudflare_api_token securely in your shell or CI secrets.
terraform init -input=false
terraform plan -out=portfolio.tfplan
terraform apply portfolio.tfplan
```

Upload your built frontend (with `index.html` at the bucket root):

```sh
aws s3 sync ./dist "s3://$(terraform output -raw bucket_name)"
aws cloudfront create-invalidation \
  --distribution-id "$(terraform output -raw cloudfront_distribution_id)" \
  --paths '/*'
```

Set appropriate object Content-Type and Cache-Control metadata during deployment. The managed cache policy has a one-second minimum TTL; use versioned asset filenames and invalidate after releases. S3 REST origins serve exact object keys; nested directory index rewriting and SPA fallback are not configured.

Keep the generated `.terraform.lock.hcl` in version control. State uses a separate, pre-created S3 backend with encryption and native locking. Bucket versioning is enabled, and Terraform will not delete a nonempty bucket. Retain ACM validation records for automatic certificate renewal.

Cloudflare provider v4 is pinned to support the requested `cloudflare_record` resource (v5 uses `cloudflare_dns_record`). Routing and validation CNAMEs are DNS-only; Cloudflare flattens the apex CNAME. Keep validation names exempt from any zone-wide CNAME flattening so ACM can see the CNAMEs. Import existing conflicting DNS records before applying. Both root and www serve the same site.

## GitHub Actions deployment

The workflow at `.github/workflows/deploy.yml` runs formatting, validation, and TFLint checks for pull requests to `main` affecting `infra/`. On pushes to `main` affecting `infra/`, it also plans against the configured S3 backend and applies the saved plan only when Terraform reports changes. Changes to the workflow itself also trigger these jobs. Frontend deployment is not part of this workflow. Commit `infra/.terraform.lock.hcl` before the first run.

Repository **Secrets**:

- `CLOUDFLARE_API_TOKEN`: token with Zone DNS Edit permission scoped to your zone.

Repository **Variables**:

- `AWS_ROLE_ARN`: deployment role assumed through GitHub OIDC.
- `AWS_REGION`: region for the website S3 bucket (for example, `us-west-2`).
- `DOMAIN_NAME`: root domain, for example `yourdomain.com`.
- `CLOUDFLARE_ZONE_ID`: Cloudflare zone ID.

One-time AWS setup: register `https://token.actions.githubusercontent.com` as an IAM OIDC provider with audience `sts.amazonaws.com`. The deployment role must trust `sts:AssumeRoleWithWebIdentity` from that provider with `StringEquals` conditions for `token.actions.githubusercontent.com:aud = sts.amazonaws.com` and `token.actions.githubusercontent.com:sub = repo:OWNER/REPOSITORY:ref:refs/heads/main`. Set its maximum session duration to at least 7200 seconds.

Grant the role permissions to manage the AWS resources in this configuration (S3, CloudFront, ACM), read managed CloudFront policies, upload/list/delete website objects, and create/read invalidations. For the backend, allow bucket listing, state-object GetObject/PutObject, and lock-object GetObject/PutObject/DeleteObject on the state key plus `.tflock`. Include KMS permissions if the backend uses a customer-managed KMS key. The state bucket and OIDC role must exist before CI runs; this stack does not bootstrap them.

If existing infrastructure was deployed with local state, migrate that state once using `terraform init -migrate-state` with the same backend settings before enabling CI. Do not let CI start with empty state for existing resources. Protect pushes to `main`, since every push can change infrastructure. The backend bucket, key, and region are explicitly configured in `infra/providers.tf`; CI does not override them.
