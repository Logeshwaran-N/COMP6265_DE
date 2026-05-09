import boto3
from botocore.exceptions import ClientError

cognito = boto3.client("cognito-idp")


def lambda_handler(event, context):
    print("EVENT:", event)

    user_pool_id = event.get("userPoolId")
    trigger_source = event.get("triggerSource")
    user_name = event.get("userName", "")
    user_attributes = event.get("request", {}).get("userAttributes", {})

    email = (user_attributes.get("email") or "").strip().lower()
    email_verified_raw = user_attributes.get("email_verified")

    # Only handle first-time external provider sign-up, e.g. Google_123456789
    if trigger_source != "PreSignUp_ExternalProvider":
        return event

    if not email:
        print("No email in external provider attributes. Skipping link.")
        return event

    # Do not block if email_verified is missing/false.
    # Some Cognito/Google mappings do not pass email_verified consistently.
    # Google OAuth already proves the user controls the Google account.
    print("External provider email:", email)
    print("External provider email_verified:", email_verified_raw)

    if "_" not in user_name:
        print("Unexpected external username format:", user_name)
        return event

    provider_name_raw, provider_user_id = user_name.split("_", 1)

    provider_name_map = {
        "google": "Google",
        "facebook": "Facebook",
        "microsoft": "Microsoft",
        "loginwithamazon": "LoginWithAmazon",
    }

    provider_name = provider_name_map.get(provider_name_raw.lower())

    if not provider_name:
        print("Provider not handled:", provider_name_raw)
        return event


    try:
        response = cognito.list_users(
            UserPoolId=user_pool_id,
            Filter=f'email = "{email}"',
            Limit=10,
        )

        users = response.get("Users", [])

        existing_user = None

        for user in users:
            username = user.get("Username", "")
            status = user.get("UserStatus", "")

            is_external_provider_user = (
                username.startswith("Google_")
                or username.startswith("Facebook_")
                or username.startswith("Microsoft_")
                or status == "EXTERNAL_PROVIDER"
            )

            if not is_external_provider_user:
                existing_user = user
                break

        if not existing_user:
            print(
                f"No existing local Cognito user found for {email}. "
                "Cognito can create a new federated user."
            )
            return event

        destination_username = existing_user.get("Username")

        print(
            f"Linking {provider_name}:{provider_user_id} "
            f"to existing Cognito user {destination_username} for {email}"
        )

        cognito.admin_link_provider_for_user(
            UserPoolId=user_pool_id,
            DestinationUser={
                "ProviderName": "Cognito",
                "ProviderAttributeValue": destination_username,
            },
            SourceUser={
                "ProviderName": provider_name,
                "ProviderAttributeName": "Cognito_Subject",
                "ProviderAttributeValue": provider_user_id,
            },
)

        return event

    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        error_message = error.response.get("Error", {}).get("Message")

        if error_code in ["AliasExistsException"]:
            print("Alias/provider already linked:", error_message)
            return event

        print("Cognito linking error:", error_code, error_message)
        raise error