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

## On-demand Minecraft launcher

The authenticated dashboard is `/tools/minecraft`, linked from Tools. It uses the existing Cognito access token; no additional shared password or GitHub token is exposed to the browser. API Gateway verifies the token signature, issuer, app client, expiry, and `openid` scope. Lambda also requires an access token. All invited Tools users can operate the launcher.

### Files and state

- `infra/minecraft-control.tf`: persistent HTTP API, Cognito authorizer, Lambda, DynamoDB operation lock, and Secrets Manager container.
- `backend/minecraft_proxy/`: allowlisted GitHub dispatcher and bounded Minecraft Java Server List Ping implementation.
- `infra/minecraft/`: independently destroyable dual-stack VPC, public subnet, game-only security group, EC2, encrypted root/world disk, and DNS-only Cloudflare A/AAAA records.
- `.github/workflows/minecraft-deploy.yml` and `minecraft-destroy.yml`: manual/launcher dispatch workflows, serialized with one shared concurrency group.
- `.github/scripts/minecraft-control.py`: operation leases, readiness and DNS verification, resource inventory, and teardown verification.
- `frontend/src/views/MinecraftView.vue`: authenticated controls, destructive-action confirmation, and 10-second telemetry polling.

Both Terraform roots use the **same existing bucket**, `458302836200-terraform-state-portfolio`. The portfolio/control plane uses `static-site/terraform.tfstate`; Minecraft uses `minecraft/terraform.tfstate`. Both use S3 native locking and encryption. Never point the Minecraft root at the portfolio state key. Destroying Minecraft does not destroy the website, login, API, or token container.

### One-time setup

1. An AWS administrator must add the reviewed permissions in `docs/minecraft-deployment-policy.json` to the existing `githubactions-portfolio` deployment role. The existing website/state permissions and OIDC main-branch trust remain required. This file scopes the Lambda execution role and secret to specific names; API Gateway and EC2 provisioning require dynamic resource IDs. Do not attach it to the runtime Lambda role, which Terraform manages with narrower permissions.
2. Create a fine-grained GitHub token limited to **Pukiretsu/portfolio**, with **Actions: Read and write** and the repository metadata access GitHub supplies. Save it as Actions repository secret **`MINECRAFT_GH_TOKEN`**. Avoid a broad classic PAT; set an expiry and rotate it when needed.
3. Keep the existing `CLOUDFLARE_API_TOKEN` secret and `AWS_ROLE_ARN`, `AWS_REGION`, `DOMAIN_NAME`, and `CLOUDFLARE_ZONE_ID` variables. The Cloudflare token needs DNS Edit for this zone. No extra state bucket is needed.
4. Read and accept the Minecraft EULA at https://aka.ms/MinecraftEULA, then set repository variable **`MINECRAFT_ACCEPT_EULA`** to **`true`**. This setting is intentionally false by default. The deploy workflow and API both enforce it.
5. Optional variables: **`MINECRAFT_VERSION`** (default `26.3`, Java Edition), **`FABRIC_LOADER_VERSION`** (default `0.19.5`), and **`FABRIC_INSTALLER_VERSION`** (default `1.1.1`). **`FABRIC_API_VERSION`** defaults to `0.166.2+26.3`. Whitelist configuration has been removed. The server uses `online-mode=false`, `enforce-secure-profile=false`, `white-list=false`, and `enforce-whitelist=false`; player names are not verified with Microsoft/Mojang and can be impersonated.
6. Push the implementation and run **Terraform infrastructure** on `main`. It creates the control plane and copies `MINECRAFT_GH_TOKEN` securely into **`portfolio/minecraft/github-token`** in AWS Secrets Manager. The secret value is a **plain token string**, not a JSON object, and is never a Terraform input or state value. Re-run this workflow after changing the token or EULA setting. Then deploy the frontend.

If storing the token manually, create the Terraform-managed container first, then use Secrets Manager's plaintext value editor for `portfolio/minecraft/github-token`. Do not pre-create a conflicting secret outside Terraform without importing it. The frontend receives only the public API URL via `auth-config.json`.

### Operating the server

Sign in, open **Tools → Minecraft**, and select **Launch Server**. The proxy accepts only the fixed deploy/destroy workflow names on `main`, acquires a conditional operation lease, and dispatches server-side with the stored credential. Duplicate or overlapping requests return a conflict. Both workflows share a GitHub concurrency group in addition to Terraform's state lock. The status endpoint probes only the tagged EC2 address, never a caller-supplied hostname or port.

Launch creates a `t4g.medium` ARM instance and encrypted 30 GiB gp3 root/world disk. Amazon Linux installs Java 21; bootstrap verifies the Mojang server checksum and downloads the pinned official Fabric launcher. Fabric runs as a non-root systemd service. No mods are bundled by default; Fabric API is a separate mod if your later mod selection requires it. No SSH, RCON, client AWS credentials, or unauthenticated API is exposed. Port 25565 is public on IPv4 and IPv6. The default server memory is 2 GiB and player limit is 10. Edit `infra/minecraft/user-data.sh.tftpl` if needed.

Connect to **`mc.angelgp.dev`** (or `mc.<DOMAIN_NAME>`) using the configured Minecraft Java version. Cloudflare proxying is disabled; CloudFront never carries the raw game connection. The public IPv4 also lets a non-VPC Lambda probe the game without a permanently billed NAT gateway. Probe latency is measured from Lambda, not from your own computer.

Provisioning includes Java installation and world generation, so expect several minutes. The workflow verifies Cloudflare A/AAAA records, public AAAA resolution, and a successful Minecraft protocol response before declaring readiness. The dashboard reports players, slots, version, and latency. Failure messages link to the workflow; bootstrap logs are in `/var/log/minecraft-bootstrap.log` on the instance. A failed apply can leave resources, so use the destroy workflow for cleanup rather than deleting the state.

**Stop / Destroy Server permanently deletes the server and its world data.** There is no backup or persistent-world promise in this version. The UI requires confirmation; manual destroy runs require the matching checkbox too. The destroy workflow snapshots resource IDs, runs `terraform destroy`, and checks terminated EC2, deleted EBS volumes, empty Minecraft state, and removed DNS records. DNS caches may retain the old address until its TTL expires.

If a dispatch times out ambiguously, the safety lease remains for up to one hour to prevent duplicate launches. Check GitHub Actions first; do not clear a lease while a workflow is still running. A workflow normally releases its lease on success/failure/cancellation. A queued run that never starts may require waiting for lease expiry.

No server launches automatically on push. Compute, EBS, and public IPv4 charges continue until Terraform teardown. The idle shutdown policy below requests that teardown automatically. The lightweight control plane and Secrets Manager container persist while the game server is offline and have their own normal AWS charges.

### Verification

```sh
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra/minecraft init -backend=false
terraform -chdir=infra/minecraft validate
terraform -chdir=infra fmt -check -recursive
python3 -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```

These checks do not launch a game server. Full deploy/destroy testing requires the new IAM permissions, token, and explicit EULA acceptance.

### Fabric idle shutdown and Terraform-managed deletion

New launches use Fabric in offline account-verification mode with no whitelist. Changing bootstrap does not replace an existing server automatically; the normal launch guard still refuses to replace a live world.

An instance-local activity monitor reads genuine join/leave log events and polls the local Minecraft status every 10 seconds, so a brief join between polls still counts. Its state is persisted on the server and sent to a per-instance DynamoDB item via an EC2 role limited to writing activity items. Old items expire automatically. The dashboard displays the server-time-based countdown, monitoring health, and an alert during the final minute.

- Before anyone has joined, the deadline is **30 empty minutes from the first successful ready check**.
- After any player has joined, the deadline is **10 continuous empty minutes**. Joining pauses the timer; the last player leaving starts a fresh 10-minute countdown.
- If a status probe fails, the monitor does not assume the server is empty. Missing or stale heartbeats block automatic cleanup.

At the deadline the monitor stops **only the Minecraft systemd process**, allowing Java to save cleanly. It does not stop or terminate EC2 and does not delete EBS or DNS. A one-minute EventBridge rule then invokes the control Lambda, which accepts only a fresh graceful-stop acknowledgement from the matching live instance and dispatches **`minecraft-destroy.yml`**. The workflow checks the instance against Terraform state and refuses automatic cleanup if Minecraft is responding again, then uses **`terraform destroy`** for every AWS and DNS resource. The same S3 bucket and `minecraft/terraform.tfstate` key remain authoritative. Resource teardown can take longer than the countdown due to schedule/runner availability.

The policy runs even with no dashboard open. Automatic teardown permanently deletes the world disk, just like manual destroy. If dispatch or Terraform cleanup fails, the stopped game instance may still incur EC2/EBS charges; inspect the linked workflow and use the normal destroy workflow to recover.

The bootstrap role/profile permissions and EventBridge rule permissions are included in the updated inline deployment policy at `docs/minecraft-deployment-policy.json` (the existing separate website policy remains required). The instance gets no permission to delete AWS resources or read the GitHub token. The runtime Lambda still only dispatches the Terraform workflow; it never calls EC2 termination APIs.

### ARM64 Minecraft installation

The `t4g.medium` bootstrap installs checksum-verified Temurin Java 25 (aarch64), Fabric, and Modrinth mods compatible with the selected Minecraft/Fabric versions. Fabric API is pinned; Lithium, FerriteCore, C2ME, ScalableLux, VMP, Chunky, and required dependencies use the latest matching release (including beta/alpha where needed). Krypton uses stable releases only and is skipped with a warning when unavailable. The deploy workflow checks required releases before Terraform apply. Required mods fail provisioning if unavailable; no incompatible fallback is installed. Managed JARs are tracked in `mods/.portfolio-managed.json`; custom JARs are preserved.

Java uses a fixed 2800M heap with G1, view distance 8, simulation distance 6, and one C2ME worker. A 2G swapfile is created only when no swap is active, with swappiness 10. Re-running the installer preserves unrelated property/TOML settings and world files, but reapplies these managed tuning/auth settings. Do not invoke the bootstrap while players are connected: it stops Java before updating files. Launching a new instance fetches the latest compatible mods and Java 25 patch; deployments are therefore not fully reproducible. Chunky is installed but pregeneration is not started automatically; monitor burst credits and memory when using it. The existing Terraform destroy workflow remains responsible for deleting AWS resources and DNS.

### Map backups and SSH access

See [Map download, restore, and private SSH access](docs/minecraft-world.md). Use `python3 scripts/minecraft-world.py download` to save only the world ZIP locally, and `upload <backup.zip> --confirm-restore` to restore it. SSH/SCP uses Systems Manager without exposing port 22.

The Minecraft **World vault** also saves and restores maps directly from `/tools/minecraft`. Private S3 backups survive server destruction; no Drive account or additional secrets are required. See [backup storage, limits, and deployment order](docs/minecraft-world.md#backups-from-the-minecraft-tool-page).
