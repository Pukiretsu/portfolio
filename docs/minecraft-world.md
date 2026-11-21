# Minecraft workspace and S3 world lifecycle

The Minecraft tool at `/tools/minecraft` has four sidebar views, with a hamburger menu on mobile:

- **Dashboard**: status, player telemetry, idle deadline, and the configuration snapshot used by the running server.
- **Start / Stop**: Start uses a saved S3 blueprint and selected world. Stop saves the world to S3 before Terraform removes EC2, EBS and DNS. Automatic idle shutdown follows the same save-before-destroy flow.
- **Configuration**: change Minecraft/Fabric/Fabric API versions, supported `server.properties` settings, enabled mods, C2ME workers, and additional mod config files. Changes are allowed only with no Minecraft resources present and no operation in progress.
- **Worlds**: download saved ZIPs any time; upload and choose the next world only while fully down. Select a map and confirm **Use selected S3 world**, or choose to generate a new world on the next Start.

## Data flow

The browser uploads ZIP parts directly into private S3; the authenticated API completes the upload only while holding an offline operation lock. No browser-to-EC2 upload or live restore is exposed. After completion the S3 upload session is closed, so old part links cannot overwrite a completed map. Incomplete multipart uploads are removed by lifecycle rules after one day. Upload sessions expire after 16 minutes.

Configuration lives in `settings/server.json`. Start takes an immutable `launches/<operation>.json` snapshot. The workflow downloads it, resolves enabled mods and exact versions, and validates the selected S3 ZIP before allocating EC2. On EC2, bootstrap fetches the trusted code, snapshot and world from S3, applies the settings, restores the map while Java is stopped, and starts Minecraft last. A running server's **Configuration** view shows both saved settings and its applied launch snapshot; manual SSH edits are not represented by that snapshot.

Stop quiesces Minecraft and the idle monitor, uploads the complete map to `backups/`, selects that backup for the next launch, then executes `terraform destroy` against the existing Minecraft backend. Failure to save blocks destruction. The persistent S3 bucket is part of the main infrastructure and survives Minecraft destruction.

ZIPs must contain `world/level.dat`; include all dimensions and player data. Minecraft 26.3 uses `world/dimensions/minecraft/the_nether` and `the_end`. Only map files are restored; mods, logs, JVM binaries and server configuration come from the selected blueprint instead. ZIP paths, symlinks, CRCs, expanded size and disk space are checked. ZIPs are limited to 1 GiB compressed and 20 GiB expanded (the instance must also have enough free disk). Changing game or mod versions does not migrate worlds; select a compatible world and keep a copy before downgrading.

## Configuration limits

The t4g.medium still uses ARM64 Temurin Java 25, a 2800M G1 heap, swap fallback, view distance up to 8 and simulation distance up to 6. C2ME workers are limited to 1–2. Fabric API is required; other supported mods can be toggled. Start validates version/mod availability before EC2 allocation.

Custom mod files are a JSON object mapping simple `.json`, `.toml` or `.properties` filenames to text, written only under `/srv/minecraft/config/`. Up to ten files, 4 KiB each, are allowed. `c2me.toml` is managed separately. These editors validate syntax/path limits, not each mod's semantic settings. Whitelist entries still require console/SSH administration if the whitelist is enabled.

## Storage and security

Bucket: `<AWS_ACCOUNT_ID>-portfolio-minecraft-backups`. Public access is blocked; TLS, encryption and versioning are enabled. Saved maps are retained indefinitely; storage charges apply. Terraform destroy protection guards the bucket. Five-minute download links are bearer links: do not share them. Cognito protects all settings, upload, download and control endpoints. AWS/GitHub credentials are never sent to the browser.

No additional GitHub secrets or variables are needed. Update the deployment role's inline policy from `docs/minecraft-deployment-policy.json`, then deploy the main infrastructure before launching Minecraft. Executable bootstrap assets under `bootstrap/` can be published only by the deployment role. The instance can read snapshots/assets/worlds and write world backups; it cannot change saved blueprints or bootstrap code.

## SSH and recovery

Private administrative SSH remains available with `python3 scripts/minecraft-world.py ssh`, using AWS CLI credentials, OpenSSH and the AWS Session Manager plugin. The helper's private key is stored locally under ignored `.local/minecraft/`; port 22 remains closed. Direct CLI upload/restore has been removed: choose and load worlds through S3 and the stopped-server page.

If a transfer is interrupted, inspect GitHub Actions and the SSM command before retrying. Active/uncertain commands retain the operation lease for safety. The `resume` SSH helper can recover paused maintenance after confirming the command has stopped. If startup fails before a map exists, use the manual **Minecraft destroy** workflow's explicitly destructive `skip_backup` recovery option. Normal page Stop and automatic idle cleanup never skip the backup. A failed stop that already saved a map can likewise be recovered after confirming that archive exists in S3.
