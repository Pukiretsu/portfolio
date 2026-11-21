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
