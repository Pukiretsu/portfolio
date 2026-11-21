# Download and restore only the Minecraft map

The transfer helper uses SSH and SCP through AWS Systems Manager. Port 22 stays closed. Terraform enables the existing AL2023 instance's SSM Agent through its instance IAM policy; the server is not replaced. Your authenticated AWS CLI identity needs `ec2:DescribeInstances`, `dynamodb:GetItem` on the control table, `ssm:SendCommand` (`AWS-RunShellScript` and the Minecraft instance), `ssm:GetCommandInvocation`, `ssm:StartSession` (`AWS-StartSSHSession` and the instance), and permission to terminate its own SSM sessions. Use your personal AWS login; frontend credentials cannot grant shell access.

Install AWS CLI, OpenSSH, Python 3, and the [AWS Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html). Run these commands from the repository root with AWS credentials active in `us-east-1`:

```bash
# Download a ZIP containing only world/ (all dimensions, player data, entities, etc.).
python3 scripts/minecraft-world.py download

# Open an interactive SSH shell on the current server.
python3 scripts/minecraft-world.py ssh

# Later, upload a previously downloaded ZIP and replace the active map.
python3 scripts/minecraft-world.py upload minecraft-backups/world-EXAMPLE.zip --confirm-restore
```

Downloads go into the ignored `minecraft-backups/` folder, or specify a destination ZIP as the second argument. Keep this copy on your own computer: Terraform destroy permanently deletes the EC2 disk and any archives kept there. The server must be running to transfer files. Never run a destroy workflow while transferring a world.

The helper discovers the current instance each time, registers a local public SSH key for `ec2-user`, and uses SCP over a Session Manager tunnel. A dedicated private key is created under ignored `.local/minecraft/` (mode 600); it is never uploaded, committed, or placed into Terraform state. To use an existing key instead, append `--identity ~/.ssh/id_ed25519` (the matching `.pub` is required). Each machine must run the helper with its own AWS login and key. The server also retains your authorized public key until it is destroyed.

Backups pause the idle monitor and gracefully stop Java to flush the map, then ZIP only the `level-name` directory from `server.properties`. Mods, JARs, service files, logs, and server configuration are excluded. The tool downloads that ZIP through SCP and restores the prior service state in a `finally` block. Players are disconnected during this brief maintenance window. Restores validate that the archive contains only `world/...`, reject traversal and symlinks, preserve the previous map in `/srv/minecraft/.world-before-import-*`, and set `minecraft:minecraft` ownership. Use backups with the same Minecraft/mod versions; restore does not downgrade or migrate worlds.

Remote ZIPs are retained under `/home/ec2-user/minecraft-transfers/`. Old map copies are retained on the instance until you explicitly remove them or destroy the server; monitor free disk space. Both locations are destroyed with EC2. Do not commit maps or private keys.

If your terminal or network is killed during a transfer, Java and the idle monitor may remain paused. Once connected again, run:

```bash
python3 scripts/minecraft-world.py resume
```

The idle countdown resumes from the end of maintenance. An interactive `ssh` shell alone does not pause the idle timer. The helper refuses transfers once an infrastructure operation or acknowledged idle shutdown is underway. Resource removal continues exclusively through Terraform.

## Backups from the Minecraft tool page

Visit `/tools/minecraft` and use **World vault**:

- **Save backup to S3** briefly stops Minecraft and stores the complete map in private S3.
- **Download ZIP** downloads a saved map even when EC2 has been destroyed.
- **Select for restore**, or choose a local ZIP and **Upload ZIP to S3**, then confirm **Restore selected world**. Launch the server first. The current world is saved to S3 before it is replaced.

All three dimensions and player data are included. Backups contain only `world/...` and must match the server's Minecraft/mod versions. ZIPs are limited to 1 GiB; uncompressed restores also need sufficient free EC2 disk space. Invalid paths, symlinks and unrelated server files are rejected before replacement. The old on-instance world is retained as a second recovery copy.

The persistent bucket is `<AWS_ACCOUNT_ID>-portfolio-minecraft-backups`, managed by the main `infra/` stack with public access blocked, TLS required, encryption and versioning enabled. Its Terraform destroy protection prevents accidental bucket deletion. Saved archives under `backups/` are retained indefinitely (S3 charges apply); use the S3 console for deletion/retention management. Temporary `uploads/` expire after one day; lifecycle deletion is asynchronous. The dashboard does not give browsers AWS keys, GitHub tokens or SSM access. Upload policies expire after 15 minutes; download links expire after 5 minutes. Do not share those bearer links.

Cognito protects every catalog/upload/download/control endpoint. Map operations dispatch the allowlisted `minecraft-backup.yml` workflow, use the same operation lock/concurrency as deploy/destroy, and execute through SSM using the instance's IAM role. Large files travel directly between the browser/S3 or EC2/S3. Lambda never receives the ZIP itself.

Deploy the main infrastructure first, then update the existing instance IAM policy through Terraform without replacing EC2. New Minecraft deployments automatically get the policy. The GitHub OIDC role also needs the updated `docs/minecraft-deployment-policy.json` inline policy for the backup bucket and tag-restricted SSM Run Command. No additional GitHub secrets or variables are required.

Keep the page open to see completion, or return later: GitHub Actions and SSM run independently. If a workflow is cancelled while its SSM command is still running, the operation lease is deliberately retained for up to one hour. Inspect the workflow/SSM command before retrying. For an interrupted restore that leaves maintenance paused, use the SSH `resume` helper after checking that the SSM command has stopped. EC2/DNS/EBS deletion is still performed exclusively through Terraform.
