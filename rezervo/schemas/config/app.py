from typing import Optional
from uuid import UUID

from pydantic import Extra

from rezervo.schemas.base import OrmBase
from rezervo.schemas.camel import CamelOrmBase

CONFIG_FILE = "config.json"


class Auth(OrmBase):
    max_attempts: int = 0


class Booking(OrmBase):
    timezone: str
    max_attempts: int = 10
    max_waiting_minutes: int = 60


class Cron(OrmBase):
    precheck_hours: int = 4
    rezervo_dir: str
    python_path: str
    log_path: str
    preparation_minutes: int = 10
    job_comment_prefix: str = "rezervo"


class Transfersh(CamelOrmBase):
    url: str


class Slack(CamelOrmBase):
    bot_token: str
    signing_secret: str
    channel_id: str


class WebPush(CamelOrmBase):
    email: str
    private_key: str


class Apprise(CamelOrmBase):
    config_file: str


class Notifications(CamelOrmBase):
    host: Optional[str] = None
    transfersh: Transfersh
    slack: Optional[Slack] = None
    web_push: Optional[WebPush] = None
    apprise: Optional[Apprise] = None


class Content(OrmBase):
    avatars_dir: Optional[str] = None


class FusionAuthMigrationFromAuth0Configuration(CamelOrmBase):
    jwt_domain: str
    management_api_client_id: str
    management_api_client_secret: str


class FusionAuthEmailConfiguration(CamelOrmBase, extra=Extra.allow):
    defaultFromName: str = "rezervo"
    defaultFromEmail: str
    host: str
    port: int
    username: str
    password: str
    security: str


class FusionAuthOAuthConfiguration(CamelOrmBase, extra=Extra.allow):
    clientSecret: str
    authorizedOriginURLs: list[str]
    authorizedRedirectURLs: list[str]
    enabledGrants: list[str]
    generateRefreshTokens: bool
    requireRegistration: bool
    logoutURL: Optional[str] = None


class FusionAuthSlidingWindowConfiguration(CamelOrmBase, extra=Extra.allow):
    maximumTimeToLiveInMinutes: int


class FusionAuthJwtConfiguration(CamelOrmBase, extra=Extra.allow):
    timeToLiveInSeconds: int
    refreshTokenTimeToLiveInMinutes: int
    refreshTokenExpirationPolicy: str
    refreshTokenSlidingWindowConfiguration: Optional[
        FusionAuthSlidingWindowConfiguration
    ] = None


class FusionAuthAdmin(CamelOrmBase):
    username: str = "admin"
    password: str


class FusionAuth(CamelOrmBase):
    admin: FusionAuthAdmin
    issuer: str
    jwt_algorithms: list[str] = ["RS256"]
    internal_url: str
    external_url: str
    application_id: UUID
    password_changed_redirect_url: Optional[str] = None
    email: FusionAuthEmailConfiguration
    jwt: FusionAuthJwtConfiguration
    oauth: FusionAuthOAuthConfiguration
    auth0_migration: Optional[FusionAuthMigrationFromAuth0Configuration] = None


class AppConfig(OrmBase):
    is_development: bool = False
    database_connection_string: str
    allowed_origins: list[str]
    auth: Auth
    booking: Booking
    cron: Cron
    content: Optional[Content] = None
    host: str
    web_host: Optional[str] = None
    fusionauth: FusionAuth
    notifications: Optional[Notifications] = None
