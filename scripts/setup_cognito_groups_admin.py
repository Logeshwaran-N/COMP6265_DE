#!/usr/bin/env python3
"""Create project Cognito groups and an initial admin user.

This script is optional, but it prevents repeated manual setup mistakes.
It uses your local AWS credentials/profile. Do not put AWS keys in the code.
"""
from __future__ import annotations

import argparse
import sys
from botocore.exceptions import ClientError
import boto3

GROUPS = ["admin", "researcher", "analyst", "data_steward", "guest"]


def ensure_group(client, pool_id: str, group: str) -> None:
    try:
        client.create_group(UserPoolId=pool_id, GroupName=group, Description=f"COMP6265 {group} role")
        print(f"created group: {group}")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "GroupExistsException":
            print(f"group exists: {group}")
        else:
            raise


def user_exists(client, pool_id: str, email: str) -> bool:
    try:
        client.admin_get_user(UserPoolId=pool_id, Username=email)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "UserNotFoundException":
            return False
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--admin-email", default="admin@test.com")
    parser.add_argument("--temp-password", default="Admin@12345")
    parser.add_argument("--send-email", action="store_true", help="Allow Cognito to send invitation email instead of suppressing it")
    args = parser.parse_args()

    client = boto3.client("cognito-idp", region_name=args.region)
    for group in GROUPS:
        ensure_group(client, args.user_pool_id, group)

    if not user_exists(client, args.user_pool_id, args.admin_email):
        kwargs = {
            "UserPoolId": args.user_pool_id,
            "Username": args.admin_email,
            "TemporaryPassword": args.temp_password,
            "UserAttributes": [
                {"Name": "email", "Value": args.admin_email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": "Platform Admin"},
            ],
        }
        if not args.send_email:
            kwargs["MessageAction"] = "SUPPRESS"
        client.admin_create_user(**kwargs)
        print(f"created admin user: {args.admin_email}")
    else:
        print(f"admin user exists: {args.admin_email}")

    client.admin_add_user_to_group(UserPoolId=args.user_pool_id, Username=args.admin_email, GroupName="admin")
    print(f"added {args.admin_email} to admin group")
    print("Done. First login may require setting a new password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
