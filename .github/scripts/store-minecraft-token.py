"""Transfer a GitHub secret to Secrets Manager without logging it or using TF state."""
import os
import subprocess
import sys

token = os.environ.get("MINECRAFT_GH_TOKEN", "").strip()
if not token:
    print("MINECRAFT_GH_TOKEN is unset. Launcher dispatch remains unavailable until configured.")
    sys.exit(0)
secret = os.environ["MINECRAFT_SECRET_ARN"]
current = subprocess.run(["aws", "secretsmanager", "get-secret-value", "--secret-id", secret, "--query", "SecretString", "--output", "text"], capture_output=True, text=True)
if current.returncode == 0 and current.stdout.strip() == token:
    print("Minecraft dispatcher credential is already current.")
    sys.exit(0)
if current.returncode and "ResourceNotFoundException" not in current.stderr:
    sys.exit("Unable to read the Minecraft dispatcher secret; check IAM permissions.")
result = subprocess.run(["aws", "secretsmanager", "put-secret-value", "--secret-id", secret, "--secret-string", "file:///dev/stdin"], input=token, capture_output=True, text=True)
if result.returncode:
    sys.exit("Unable to store the Minecraft dispatcher credential; check IAM permissions.")
print("Minecraft dispatcher credential stored securely.")
