import uuid
from functools import lru_cache

from auth0.authentication import GetToken
from auth0.management import Auth0
from auth0.rest import RestClientOptions
from fusionauth.fusionauth_client import FusionAuthClient

from rezervo import models
from rezervo.database.database import SessionLocal
from rezervo.schemas.config.app import CONFIG_FILE
from rezervo.schemas.config.config import read_app_config
from rezervo.settings import get_settings
from rezervo.utils.logging_utils import log


@lru_cache()
def get_fusionauth_client():
    return FusionAuthClient(
        get_settings().FUSIONAUTH_API_KEY, read_app_config().fusionauth.internal_url
    )


def retrieve_all_auth0_user_emails(user_ids: list[str]):
    auth0_client = get_auth0_management_client()
    auth0_user_emails = {}
    per_page = 50  # Auth0 max per_page is 50
    page = 0
    query = f"user_id:({' OR '.join(user_ids)})"
    while True:
        page_res = auth0_client.users.list(
            page=page, per_page=per_page, q=query, fields=["user_id", "email"]
        )
        for user in page_res["users"]:
            auth0_user_emails[user["user_id"]] = user["email"]
        if (
            len(auth0_user_emails) >= page_res["total"]
            or page_res["length"] < page_res["limit"]
        ):
            break
        page += 1
    return auth0_user_emails


def migrate_from_auth0():
    with SessionLocal() as db:
        auth0_users = (
            db.query(models.User).filter(models.User.jwt_sub.startswith("auth0|")).all()
        )
        if len(auth0_users) == 0:
            log.info("No Auth0 users found in the users table, skipping migration")
            return
        log.debug(
            f"Found {len(auth0_users)} Auth0 user{'s' if len(auth0_users) > 1 else ''} in the users table"
        )
        fusionauth_client = get_fusionauth_client()
        auth0_user_emails = retrieve_all_auth0_user_emails(
            [user.jwt_sub for user in auth0_users]
        )
        for user in auth0_users:
            user_email = auth0_user_emails.get(user.jwt_sub)
            if not user_email:
                log.error(
                    f"Failed to retrieve email for Auth0 user '{user.name}' with sub '{user.jwt_sub}'"
                )
                continue
            user_res = fusionauth_client.retrieve_user_by_email(user_email)
            if user_res.was_successful():
                # user already exists in FusionAuth, but 'jwt_sub' needs to be updated
                fusionauth_user = user_res.success_response["user"]
                fusionauth_user_id = fusionauth_user["id"]
                if not fusionauth_user_id:
                    log.error(
                        f"User '{user.name}' is registered in FusionAuth, but user response is missing an id"
                    )
                    continue
                user.jwt_sub = fusionauth_user_id
                log.info(
                    f"Updated user {user.name} with FusionAuth user id {fusionauth_user_id}"
                )
                continue
            # generate new user id for fusionauth
            fusionauth_user_id = uuid.uuid4()
            # create a new user in fusionauth with auth0 data and generated id
            create_res = fusionauth_client.create_user(
                {
                    "user": {
                        "email": user_email,
                        "username": user.name,
                    },
                    "sendSetPasswordEmail": True,
                },
                fusionauth_user_id,
            )
            if not create_res.was_successful():
                log.error(
                    f"Failed to create FusionAuth user for '{user.name}': {create_res.error_response}"
                )
            else:
                # update the user table sub column with the fusionauth id
                user.jwt_sub = fusionauth_user_id
                log.info(f"Migrated user '{user.name}' to FusionAuth")
        db.commit()


@lru_cache()
def get_auth0_management_client() -> Auth0:
    migration_config = read_app_config().fusionauth.auth0_migration
    if migration_config is None:
        raise ValueError(f"Auth0 migration configuration not found in {CONFIG_FILE}")
    domain = migration_config.jwt_domain
    client_id = migration_config.management_api_client_id
    client_secret = migration_config.management_api_client_secret
    if domain is None or client_id is None or client_secret is None:
        raise ValueError(
            "Auth0 management API client credentials not configured correctly"
        )
    mgmt_api_token = GetToken(
        domain=domain,
        client_id=client_id,
        client_secret=client_secret,
    ).client_credentials(audience=f"https://{domain}/api/v2/")["access_token"]
    return Auth0(domain, mgmt_api_token, RestClientOptions(timeout=20.0))
