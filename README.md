# Portfolio infrastructure

Repository for my DevOps portfolio.

## Frontend

The Vue application lives in `frontend/`. Run `npm ci` and `npm run dev` from that folder to develop locally; `npm run build` generates `frontend/dist/`.

The **Deploy frontend** workflow (`.github/workflows/frontend.yml`) builds pull requests and deploys frontend changes pushed to `main`. You can also select **Actions → Deploy frontend → Run workflow** on `main`. It uses the existing AWS OIDC role and repository variables `BUCKET_NAME` and `CLOUDFRONT_DISTRIBUTION_ID`, configured with the deployed infrastructure outputs. Update those variables if the bucket or distribution is replaced. No Cloudflare token is required for frontend deployments.

Versioned assets are uploaded before HTML and cached as immutable. HTML is revalidated, and the workflow waits for CloudFront invalidation. Older hashed assets are retained for visitors with an older page; S3 versioning also retains prior uploads.

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

One-time AWS setup: register `https://token.actions.githubusercontent.com` as an IAM OIDC provider with audience `sts.amazonaws.com`. The deployment role must trust `sts:AssumeRoleWithWebIdentity` from that provider with `StringEquals` conditions for `token.actions.githubusercontent.com:aud = sts.amazonaws.com` and `token.actions.githubusercontent.com:sub = repo:Pukiretsu@67608563/portfolio@1460066710:ref:refs/heads/main`. Set its maximum session duration to at least 7200 seconds.

Grant the role permissions to manage the AWS resources in this configuration (S3, CloudFront, ACM), read managed CloudFront policies, upload/list/delete website objects, and create/read invalidations. For the backend, allow bucket listing, state-object GetObject/PutObject, and lock-object GetObject/PutObject/DeleteObject on the state key plus `.tflock`. Include KMS permissions if the backend uses a customer-managed KMS key. The state bucket and OIDC role must exist before CI runs; this stack does not bootstrap them.

If existing infrastructure was deployed with local state, migrate that state once using `terraform init -migrate-state` with the same backend settings before enabling CI. Do not let CI start with empty state for existing resources. Protect pushes to `main`, since every push can change infrastructure. The backend bucket, key, and region are explicitly configured in `infra/providers.tf`; CI does not override them.

The current GitHub OIDC subject includes immutable owner and repository IDs, as confirmed in CloudTrail. The deployment role also has the supplemental permissions in `docs/deployment-role-permissions.json`, in addition to the existing `website-hosting` policy. Its trust policy is recorded in `docs/deployment-role-trust.json`. These bootstrap IAM settings are managed outside the website Terraform stack.

## Personal Tools and Cognito

Terraform is split by service while retaining existing resource addresses:

- `infra/main.tf`: shared data sources.
- `infra/storage.tf`: private S3 bucket and its access policy.
- `infra/cdn.tf` and `infra/functions/spa-routes.js`: CloudFront, OAC, and explicit Vue route rewrites.
- `infra/certificates.tf`: ACM certificates and validation waiter.
- `infra/dns.tf`: Cloudflare routing and ACM validation records.
- `infra/cognito.tf`: invitation-only user pool, public OAuth client, hosted login domain, and public runtime configuration.
- `infra/providers.tf`, `infra/variables.tf`, `infra/outputs.tf`: providers/backend, inputs, and outputs.

Visit `/tools` to sign in via `/login`. Cognito handles passwords, password reset, initial password changes, and mandatory authenticator-app MFA enrollment. The browser uses authorization code + PKCE, state, and nonce through `oidc-client-ts`. The public client has no secret. Tokens are kept in tab-scoped sessionStorage, expire after 15 minutes, and are removed on logout or expiry. Logout revokes the refresh token and clears the hosted login session. Cognito-issued JWTs are not instantly invalidated for every external verifier by logging out; future APIs must enforce expiry and their own authorization policy.

Set repository Actions secret **`TOOLS_ADMIN_EMAIL`** to the address you want to invite. On the next infrastructure run, the workflow creates that user only if it does not exist and Cognito emails a generated temporary password. Complete the password change and register an authenticator when signing in. Neither passwords nor the account email are Terraform variables or state. If you add the secret later, use **Actions → Terraform infrastructure → Run workflow → main**; even an unchanged plan checks for the invitation. Existing users are not recreated or resent invitations. Changing the secret can invite another user; it does not delete previous users. Manage users and invitation resends in the Cognito console. Never put temporary or permanent passwords in GitHub secrets or Terraform configuration.

`/auth-config.json` contains only the public issuer, app-client ID, and Cognito domain, is managed by Terraform, and bypasses CloudFront caching. The frontend upload workflow intentionally preserves this object. Both root and www have exact callback and logout URLs. Localhost is not registered by default; use a separate development app client for local sign-in testing.

The Tools route is a client-side sign-in gate over a public static application. It does not make downloaded HTML/JS private or grant AWS credentials. The starter JSON workbench runs only in the browser. Any future tool that accesses private data or executes cloud operations must use a backend that validates the Cognito access token's signature, issuer, expiry, token_use, client ID, and required permissions. Do not put private data or service secrets in the static bundle. No unauthenticated Cognito identity pool is provisioned.

The Cognito user pool has deletion protection and Terraform `prevent_destroy`. Do not disable them unless intentionally deleting accounts. The deployment role's additional Cognito and CloudFront-function permissions are recorded in `docs/deployment-role-permissions.json` and must be applied by an administrator before the first run.
