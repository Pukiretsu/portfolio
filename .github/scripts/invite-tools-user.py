"""Invite a private Cognito user without storing their password or email in state."""

import json
import os
import subprocess
import sys


def main():
    email = os.environ.get("TOOLS_ADMIN_EMAIL", "").strip().lower()
    if not email:
        print("TOOLS_ADMIN_EMAIL is unset; personal account invitation skipped.")
        return 0

    pool = os.environ["COGNITO_USER_POOL_ID"]
    base = ["aws", "cognito-idp"]
    identity = ["--user-pool-id", pool, "--username", email]
    lookup = subprocess.run(base + ["admin-get-user"] + identity, capture_output=True, text=True)
    if lookup.returncode == 0:
        print("The personal account already exists; no invitation sent.")
        return 0
    if "UserNotFoundException" not in lookup.stderr:
        print("Cognito account lookup failed. Check the deployment role's AdminGetUser permission.", file=sys.stderr)
        return 1

    # Cognito generates the temporary password and delivers it by email.
    attributes = [{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}]
    create = subprocess.run(
        base + ["admin-create-user"] + identity
        + ["--desired-delivery-mediums", "EMAIL", "--user-attributes", json.dumps(attributes)],
        capture_output=True, text=True,
    )
    if create.returncode and "UsernameExistsException" not in create.stderr:
        print("Cognito invitation failed. Check IAM permissions and Cognito email delivery limits.", file=sys.stderr)
        return 1
    print("The personal account is ready. Check the configured mailbox for the invitation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
