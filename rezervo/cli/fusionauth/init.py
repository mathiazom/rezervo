from functools import lru_cache

from fusionauth.fusionauth_client import FusionAuthClient  # type: ignore

from rezervo.cli.async_cli import AsyncTyper
from rezervo.cli.fusionauth.consts import (
    FUSIONAUTH_APPLICATION_NAME,
    FUSIONAUTH_DEFAULT_APPLICATION_NAME,
    FUSIONAUTH_DEFAULT_THEME_NAME,
    FUSIONAUTH_RESET_PASSWORD_EMAIL_TEMPLATE_ID,
    FUSIONAUTH_RESET_PASSWORD_EMAIL_TEMPLATE_NAME,
    FUSIONAUTH_SETUP_PASSWORD_EMAIL_TEMPLATE_ID,
    FUSIONAUTH_SETUP_PASSWORD_EMAIL_TEMPLATE_NAME,
    FUSIONAUTH_THEME_ID,
    FUSIONAUTH_THEME_NAME,
    FUSIONAUTH_USER_CREATED_EVENT_TYPE,
    FUSIONAUTH_USER_DELETED_EVENT_TYPE,
    FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_ID,
    FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_URL_PATH,
)
from rezervo.cli.fusionauth.templates import (
    HtmlAndPlainText,
    build_change_password_email_template,
    build_forgot_password_submit_template,
    build_setup_password_complete_template,
)
from rezervo.schemas.config.config import read_app_config
from rezervo.settings import get_settings
from rezervo.utils.logging_utils import log

app_config = read_app_config()
fusionauth_config = app_config.fusionauth
FUSIONAUTH_EXTERNAL_URL = fusionauth_config.external_url

init_fusionauth_cli = AsyncTyper()


@lru_cache()
def get_fusionauth_client():
    return FusionAuthClient(
        get_settings().FUSIONAUTH_API_KEY, fusionauth_config.internal_url
    )


def init():
    init_system()
    init_theme()
    init_email_templates()
    init_tenant()
    init_user_created_webhook()
    init_application()
    init_admin_user()


def init_system():
    log.info("init system")
    client = get_fusionauth_client()
    res = client.patch_system_configuration(
        {
            "systemConfiguration": {
                "corsConfiguration": {
                    "enabled": True,
                    "allowCredentials": True,
                    "allowedMethods": [
                        "GET",
                        "POST",
                    ],
                    "allowedOrigins": [
                        FUSIONAUTH_EXTERNAL_URL,
                    ],
                }
            }
        }
    )
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)


def init_theme():
    log.info("init theme")
    client = get_fusionauth_client()
    retrieve_res = client.retrieve_theme(FUSIONAUTH_THEME_ID)
    if retrieve_res.was_successful():
        log.info("theme already exists, patching")
    else:
        theme_res = client.retrieve_themes()
        if not theme_res.was_successful():
            log.error(theme_res.error_response)
            return
        default_theme_id = None
        themes = theme_res.success_response.get("themes")
        exists = False
        if themes is not None:
            for theme in themes:
                if theme.get("name") == FUSIONAUTH_THEME_NAME:
                    log.info("theme already exists, patching")
                    exists = True
                elif theme.get("name") == FUSIONAUTH_DEFAULT_THEME_NAME:
                    default_theme_id = theme.get("id")
        if not exists:
            if default_theme_id is None:
                log.error("no default theme found")
                return
            duplicate_theme_config = {
                "sourceThemeId": default_theme_id,
                "theme": {
                    "name": FUSIONAUTH_THEME_NAME,
                },
            }
            res = client.create_theme(duplicate_theme_config, FUSIONAUTH_THEME_ID)
            if not res.was_successful():
                log.error(res.error_response)
                return
    patch_res = client.patch_theme(
        FUSIONAUTH_THEME_ID,
        {
            "theme": {
                "templates": {
                    "passwordComplete": build_setup_password_complete_template(
                        fusionauth_config.password_changed_redirect_url
                    ),
                    "passwordForgot": build_forgot_password_submit_template(
                        fusionauth_config.password_changed_redirect_url
                    ),
                }
            }
        },
    )
    if patch_res.was_successful():
        log.info("OK")
        return
    log.error(patch_res.error_response)


def init_email_template(
    template_id: str, name: str, subject: str, body: HtmlAndPlainText
):
    log.info(f"init '{name}' email template")
    client = get_fusionauth_client()
    email_template_config = {
        "emailTemplate": {
            "name": name,
            "defaultSubject": subject,
            "defaultHtmlTemplate": body.html,
            "defaultTextTemplate": body.plain_text,
        }
    }
    templates_res = client.retrieve_email_templates()
    if not templates_res.was_successful():
        log.error(templates_res.error_response)
        return
    templates = templates_res.success_response.get("emailTemplates")
    if templates is not None:
        for template in templates:
            if template.get("name") == name or template.get("id") == template_id:
                log.info(f"email template '{name}' already exists, patching")
                res = client.patch_email_template(template_id, email_template_config)
                if res.was_successful():
                    log.info("OK")
                    return
                log.error(res.error_response)
                return
    res = client.create_email_template(email_template_config, template_id)
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)


def init_email_templates():
    app_id = fusionauth_config.application_id
    init_email_template(
        FUSIONAUTH_SETUP_PASSWORD_EMAIL_TEMPLATE_ID,
        FUSIONAUTH_SETUP_PASSWORD_EMAIL_TEMPLATE_NAME,
        "Aktiver rezervo-bruker",
        build_change_password_email_template(
            FUSIONAUTH_EXTERNAL_URL,
            HtmlAndPlainText(
                html="Klikk på lenken under for å aktivere din rezervo-bruker.",
                plain_text="Naviger til lenken under for å aktivere din rezervo-bruker.",
            ),
            app_id,
            fusionauth_config.password_changed_redirect_url,
        ),
    )
    init_email_template(
        FUSIONAUTH_RESET_PASSWORD_EMAIL_TEMPLATE_ID,
        FUSIONAUTH_RESET_PASSWORD_EMAIL_TEMPLATE_NAME,
        "Tilbakestill passord",
        build_change_password_email_template(
            FUSIONAUTH_EXTERNAL_URL,
            HtmlAndPlainText(
                html="Klikk på lenken under for å sette et nytt passord for din rezervo-bruker.",
                plain_text="Naviger til lenken under for å sette et nytt passord for din rezervo-bruker.",
            ),
            app_id,
            fusionauth_config.password_changed_redirect_url,
        ),
    )


def init_tenant():
    log.info("init tenant")
    client = get_fusionauth_client()
    tenant_id = get_settings().FUSIONAUTH_DEFAULT_TENANT_ID
    log.debug(f"tenant id: {tenant_id}")
    tenant_config = {
        "tenant": {
            "issuer": fusionauth_config.issuer,
            "themeId": FUSIONAUTH_THEME_ID,
            "eventConfiguration": {
                "events": {
                    FUSIONAUTH_USER_CREATED_EVENT_TYPE: {
                        "enabled": True,
                    },
                    FUSIONAUTH_USER_DELETED_EVENT_TYPE: {
                        "enabled": True,
                    },
                }
            },
            "emailConfiguration": {
                "setPasswordEmailTemplateId": FUSIONAUTH_SETUP_PASSWORD_EMAIL_TEMPLATE_ID,
                "forgotPasswordEmailTemplateId": FUSIONAUTH_RESET_PASSWORD_EMAIL_TEMPLATE_ID,
                **fusionauth_config.email.dict(by_alias=True),
            },
        }
    }
    res = client.patch_tenant(tenant_id, tenant_config)
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)


def init_user_created_webhook():
    log.info("init 'user.create.complete' webhook")
    client = get_fusionauth_client()
    webhooks_res = client.retrieve_webhooks()
    if not webhooks_res.was_successful():
        log.error(webhooks_res.error_response)
        return
    webhook_config = {
        "webhook": {
            "id": FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_ID,
            "url": f"{app_config.host}/{FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_URL_PATH}",
            "tenantIds": [get_settings().FUSIONAUTH_DEFAULT_TENANT_ID],
            "connectTimeout": 5000,
            "readTimeout": 10000,
            "eventsEnabled": {
                FUSIONAUTH_USER_CREATED_EVENT_TYPE: True,
                FUSIONAUTH_USER_DELETED_EVENT_TYPE: True,
            },
        }
    }
    webhooks = webhooks_res.success_response.get("webhooks")
    if webhooks is not None:
        for webhook in webhooks:
            if webhook.get("id") == FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_ID:
                log.info("webhook already exists, updating")
                res = client.update_webhook(
                    FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_ID, webhook_config
                )
                if res.was_successful():
                    log.info("OK")
                    return
                log.error(res.error_response)
                return
    res = client.create_webhook(webhook_config, FUSIONAUTH_USER_LIFECYCLE_WEBHOOK_ID)
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)


def init_application():
    log.info("init application")
    client = get_fusionauth_client()
    apps_res = client.retrieve_applications()
    if not apps_res.was_successful():
        log.error(apps_res.error_response)
        return
    app_id = fusionauth_config.application_id
    log.debug(f"application id: {app_id}")
    log.debug(f"application name: {FUSIONAUTH_APPLICATION_NAME}")
    application_config = {
        "application": {
            "name": FUSIONAUTH_APPLICATION_NAME,
            "oauthConfiguration": {
                **fusionauth_config.oauth.dict(by_alias=True),
            },
            "jwtConfiguration": {
                "enabled": True,
                **fusionauth_config.jwt.dict(by_alias=True),
            },
            "loginConfiguration": {
                "allowTokenRefresh": True,
                "generateRefreshTokens": True,
                "requireAuthentication": True,
            },
        }
    }
    apps = apps_res.success_response.get("applications")
    if apps is not None:
        for app in apps:
            if (
                app.get("name") == FUSIONAUTH_APPLICATION_NAME
                or app.get("id") == app_id
            ):
                log.info("application already exists, updating")
                update_res = client.update_application(app_id, application_config)
                if update_res.was_successful():
                    log.info("OK")
                    return
                log.error(update_res.error_response)
                return
    res = client.create_application(application_config, app_id)
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)


def init_admin_user():
    log.info("init admin user")
    client = get_fusionauth_client()
    admin_res = client.retrieve_user_by_username("admin")
    if admin_res.was_successful():
        log.info("admin user already exists")
        return
    apps_res = client.retrieve_applications()
    if not apps_res.was_successful():
        log.error(apps_res.error_response)
        return
    apps = apps_res.success_response.get("applications")
    if apps is None:
        log.error("No applications found")
        return
    app_id = None
    for app in apps:
        if app.get("name") == FUSIONAUTH_DEFAULT_APPLICATION_NAME:
            app_id = app.get("id")
            break
    if app_id is None:
        log.error("No FusionAuth application found")
        return
    log.debug(f"'FusionAuth' application: {app_id}")
    res = client.register(
        {
            "user": {
                "username": fusionauth_config.admin.username,
                "password": fusionauth_config.admin.password,
            },
            "registration": {
                "applicationId": app_id,
                "roles": ["admin"],
            },
            "skipVerification": True,
        }
    )
    if res.was_successful():
        log.info("OK")
        return
    log.error(res.error_response)
