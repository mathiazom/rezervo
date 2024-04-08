import asyncio
import json
import re
import time
from datetime import datetime
from typing import Mapping, Optional, Sequence, Union
from uuid import UUID

import humanize
import pytz
from playwright.async_api import (
    Cookie,
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from pydantic import ValidationError
from pydantic.fields import Field
from pydantic.main import BaseModel

from rezervo import models
from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.errors import AuthenticationError
from rezervo.http_client import HttpClient
from rezervo.providers.ibooking.urls import (
    AUTH_URL,
    BOOKING_URL,
    SIT_AUTH_COOKIE_URL,
    SIT_LOGIN_URL,
    SIT_OIDC_USER_COOKIE_ORIGIN,
    TOKEN_VALIDATION_URL,
)
from rezervo.schemas.camel import CamelModel
from rezervo.schemas.config.user import ChainIdentifier, ChainUser
from rezervo.utils.logging_utils import log
from rezervo.utils.playwright_utils import (
    playwright_trace_start,
    playwright_trace_stop,
)

WAIT_FOR_TOTP_MILLISECONDS = 200
WAIT_FOR_TOTP_MAX_SECONDS = 5 * 60
WAIT_FOR_TOTP_VERIFICATION_MILLISECONDS = 200
WAIT_FOR_TOTP_VERIFICATION_MAX_SECONDS = 60
WAIT_FOR_FRESH_COOKIES_MILLISECONDS = 100
WAIT_FOR_FRESH_COOKIES_MAX_SECONDS = 30

IBOOKING_TOKEN_LIFETIME_SECONDS = 60 * 60
IBOOKING_TOKEN_REFRESH_THRESHOLD_SECONDS = 10 * 60
SIT_ACCESS_TOKEN_LIFETIME_SECONDS = 60 * 60
SIT_ACCESS_TOKEN_REFRESH_THRESHOLD_SECONDS = 10 * 60
SIT_REFRESH_TOKEN_LIFETIME_SECONDS = 24 * 60 * 60


class ExpiringToken(BaseModel):
    token: str
    expires_at: int


class IBookingAuthData(BaseModel):
    access_token: ExpiringToken
    ibooking_token: ExpiringToken
    refresh_token: ExpiringToken
    cookies: Sequence[Mapping]


class SitAuthRefreshResult(CamelModel):
    access_token: str
    refresh_token: str
    refresh_token_expires_in: int


async def fetch_public_ibooking_token() -> Union[str, AuthenticationError]:
    async with HttpClient.singleton().get(BOOKING_URL) as booking_res:
        booking_soup = await booking_res.text()
    token_matches = re.search(r'\s+clientToken\s*=\s*"([^"]+)"', booking_soup)
    if token_matches is None:
        return AuthenticationError.TOKEN_EXTRACTION_FAILED
    try:
        return token_matches.group(1)
    except IndexError:
        return AuthenticationError.TOKEN_EXTRACTION_FAILED


async def get_ibooking_token_from_access_token(
    access_token: str,
) -> Optional[ExpiringToken]:
    async with HttpClient.singleton().post(
        AUTH_URL,
        headers={"Content-Type": "application/json", "x-b2c-token": access_token},
    ) as res:
        if not res.ok:
            return None
        data = await res.json()
        return ExpiringToken(
            token=data["accessToken"],
            expires_at=int(time.time()) + IBOOKING_TOKEN_LIFETIME_SECONDS,
        )


async def validate_ibooking_token(ibooking_token: str):
    async with HttpClient.singleton().post(
        TOKEN_VALIDATION_URL,
        data={"token": ibooking_token},
    ) as res:
        if not res.ok:
            return False, None
        token_info = await res.json()
    if "authTokenExpires" not in token_info:
        return False, None
    expires_string = token_info["authTokenExpires"]
    expires_at = int(
        datetime.strptime(expires_string, "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=pytz.timezone("Europe/Oslo"))
        .timestamp()
    )
    return True, expires_at


class SitAuthRefreshTokens(BaseModel):
    access_token: ExpiringToken
    refresh_token: ExpiringToken


async def get_tokens_from_refresh_token(
    refresh_token: str,
) -> Optional[SitAuthRefreshTokens]:
    async with HttpClient.singleton().post(
        f"{SIT_AUTH_COOKIE_URL}/sitnettprodb2c.onmicrosoft.com/oauth2/v2.0/token?p=b2c_1_si_email"
        f"&client_id=1fd8cf25-b13b-4bbe-a673-809725291c9c"
        f"&grant_type=refresh_token"
        f"&scope=https%3A%2F%2Fsitnettprodb2c.onmicrosoft.com%2F2390d625-e415-4049-a300-3fab18caa9d2%2Fuser_impersonation+offline_access+openid+profile"
        f"&refresh_token={refresh_token}"
    ) as res:
        if not res.ok:
            return None
        data = SitAuthRefreshResult(**await res.json())
        current_time = int(time.time())
        return SitAuthRefreshTokens(
            access_token=ExpiringToken(
                token=data.access_token,
                expires_at=current_time + SIT_ACCESS_TOKEN_LIFETIME_SECONDS,
            ),
            refresh_token=ExpiringToken(
                token=data.refresh_token,
                expires_at=current_time + data.refresh_token_expires_in,
            ),
        )


async def refresh_chain_user_auth_data(
    chain_user: ChainUser,
) -> Union[IBookingAuthData, AuthenticationError]:
    if chain_user.auth_data is None:
        log.warning(
            f"Auth data not found for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return AuthenticationError.MISSING_TOTP_SESSION
    try:
        auth_data = IBookingAuthData(**json.loads(chain_user.auth_data))
    except (json.JSONDecodeError, ValidationError):
        log.error(
            f"Invalid auth data for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return AuthenticationError.MISSING_TOTP_SESSION
    current_time = int(time.time())
    if (
        current_time
        < auth_data.access_token.expires_at - SIT_ACCESS_TOKEN_REFRESH_THRESHOLD_SECONDS
        and current_time
        < auth_data.ibooking_token.expires_at - IBOOKING_TOKEN_REFRESH_THRESHOLD_SECONDS
    ):
        # stored tokens are fresh enough, skipping refresh
        return auth_data
    if current_time > auth_data.refresh_token.expires_at:
        log.warning(
            f"Refresh token expired for '{chain_user.chain}' user '{chain_user.username}', extending session..."
        )
        extend_res = await extend_auth_session_silently(
            chain_user.chain, chain_user.user_id
        )
        if extend_res is None:
            log.critical(
                f"Refresh token expired and session extension failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return AuthenticationError.TOKEN_INVALID
        auth_data = extend_res
    refresh_res = await get_tokens_from_refresh_token(auth_data.refresh_token.token)
    if refresh_res is None:
        log.error(
            f"Access token refresh failed for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return AuthenticationError.TOKEN_INVALID
    ibooking_token = await get_ibooking_token_from_access_token(
        refresh_res.access_token.token
    )
    if ibooking_token is None:
        log.error(
            f"Ibooking token extraction failed for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return AuthenticationError.TOKEN_EXTRACTION_FAILED
    with SessionLocal() as db:
        db_chain_user = crud.get_db_chain_user(db, chain_user.chain, chain_user.user_id)
        if db_chain_user is None:
            log.error(f"'{chain_user.chain} user not found for '{chain_user.username}'")
            return AuthenticationError.ERROR
        refreshed_auth_res = IBookingAuthData(
            access_token=refresh_res.access_token,
            refresh_token=refresh_res.refresh_token,
            ibooking_token=ibooking_token,
            cookies=auth_data.cookies,
        )
        db_chain_user.auth_data = refreshed_auth_res.json()
        db.commit()
    return refreshed_auth_res


class SitAuthOIDCData(BaseModel):
    access_token: str
    access_token_expires_at: int = Field(..., alias="expires_at")
    refresh_token: str


async def extract_auth_tokens(page: Page) -> Optional[SitAuthOIDCData]:
    """
    Extracts the access and refresh tokens from the local storage
    """
    storage_state = await page.context.storage_state()
    for origin_state in storage_state["origins"]:
        if origin_state["origin"] == SIT_OIDC_USER_COOKIE_ORIGIN:
            local_storage = origin_state["localStorage"]
            if local_storage is None:
                return None
            for entry in local_storage:
                if entry["name"].startswith(f"oidc.user:{SIT_AUTH_COOKIE_URL}"):
                    return SitAuthOIDCData(**json.loads(entry["value"]))
            break
    return None


async def extract_cookies_from_url(page: Page, url) -> list[Cookie]:
    return await page.context.cookies(url)


async def inject_cookies_from_url(page: Page, url, cookies: Sequence[Mapping]):
    await page.context.add_cookies(cookies)  # type: ignore


async def authenticate_with_session_cookies(
    page: Page, cookies: Sequence[Mapping]
) -> Optional[SitAuthRefreshTokens]:
    """
    initiate a non-interactive login
    """
    await inject_cookies_from_url(page, SIT_AUTH_COOKIE_URL, cookies)
    await page.goto(SIT_LOGIN_URL)
    await page.get_by_title("Logg inn med e-post").click(timeout=10000)
    wait_start = asyncio.get_event_loop().time()
    while (
        asyncio.get_event_loop().time() - wait_start
    ) < WAIT_FOR_FRESH_COOKIES_MAX_SECONDS:
        res = await extract_auth_tokens(page)
        if res is not None:
            return SitAuthRefreshTokens(
                access_token=ExpiringToken(
                    token=res.access_token,
                    expires_at=res.access_token_expires_at,
                ),
                refresh_token=ExpiringToken(
                    token=res.refresh_token,
                    expires_at=int(time.time()) + SIT_REFRESH_TOKEN_LIFETIME_SECONDS,
                ),
            )
        await page.wait_for_timeout(WAIT_FOR_FRESH_COOKIES_MILLISECONDS)
    return None


async def verify_sit_credentials(username: str, password: str):
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        context = await browser.new_context()
        await playwright_trace_start(context)
        page = await context.new_page()
        try:
            await init_login_with_credentials(page, username, password)
            valid = await page.locator("button[id='sendCode']").is_enabled(
                timeout=10000
            )
        except PlaywrightTimeoutError:
            valid = False
        await playwright_trace_stop(context, "verify_sit_creds")
        return valid


async def init_login_with_credentials(page: Page, username: str, password: str):
    await page.goto(SIT_LOGIN_URL)
    await page.get_by_title("Logg inn med e-post").click(timeout=30000)
    await page.locator("#email").fill(username, timeout=10000)
    await page.locator("#password").fill(password, timeout=10000)
    await page.locator("button[id='next']").click(timeout=10000)


async def login_with_totp(chain_user: ChainUser) -> Optional[IBookingAuthData]:
    if chain_user.password is None:
        log.error(
            f"Invalid '{chain_user.chain}' user credentials for '{chain_user.username}', password not found"
        )
        return None
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        context = await browser.new_context()
        await playwright_trace_start(context)
        page = await context.new_page()
        await init_login_with_credentials(
            page, chain_user.username, chain_user.password
        )
        await page.locator("button[id='sendCode']").click(timeout=30000)
        totp_wait_start = asyncio.get_event_loop().time()
        with SessionLocal() as db:
            while (
                asyncio.get_event_loop().time() - totp_wait_start
            ) < WAIT_FOR_TOTP_MAX_SECONDS:
                totp = crud.get_chain_user_totp(
                    db, chain_user.chain, chain_user.user_id
                )
                if totp is not None:
                    break
                await page.wait_for_timeout(WAIT_FOR_TOTP_MILLISECONDS)
        if totp is None:
            log.error(
                f"TOTP not provided for '{chain_user.chain}' user '{chain_user.username}' (waited {WAIT_FOR_TOTP_MAX_SECONDS} seconds)"
            )
            await playwright_trace_stop(context, "login_totp_not_provided")
            return None
        if len(totp) != 6 or not totp.isdigit():
            log.error(
                f"Invalid TOTP code from '{chain_user.chain}' user '{chain_user.username}'"
            )
            await playwright_trace_stop(context, "login_totp_invalid")
            return None
        await page.locator("#verificationCode").fill(totp, timeout=10000)
        await page.locator("button[id='verifyCode']").click(timeout=10000)
        await page.wait_for_url(SIT_LOGIN_URL, timeout=10000)
        cookies = await extract_cookies_from_url(page, SIT_AUTH_COOKIE_URL)
        await playwright_trace_stop(context, "login_totp")
        await context.close()
        verification_context = await browser.new_context()
        await playwright_trace_start(verification_context)
        verification_page = await verification_context.new_page()
        verification_res = await authenticate_with_session_cookies(
            verification_page, cookies
        )
        await playwright_trace_stop(verification_context, "login_totp_verification")
        await verification_context.close()
        if verification_res is None:
            log.error(
                f"TOTP flow verification failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
    ibooking_token = await get_ibooking_token_from_access_token(
        verification_res.access_token.token
    )
    if ibooking_token is None:
        log.error(
            f"Could not retrieve ibooking token from access token for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return None
    return IBookingAuthData(
        access_token=verification_res.access_token,
        refresh_token=verification_res.refresh_token,
        ibooking_token=ibooking_token,
        cookies=cookies,
    )


async def initiate_auth_session_interactively(
    chain_identifier: ChainIdentifier, user_id: UUID
):
    """
    Performs authentication with email, password and TOTP code.
    Requires user interaction to retrieve TOTP code.
    """
    with SessionLocal() as db:
        chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if chain_user is None:
            log.error(f"'{chain_identifier}' user not found for id '{user_id}'")
            return
        crud.delete_chain_user_totp(db, chain_user.chain, chain_user.user_id)
    auth_data = await login_with_totp(chain_user)
    with SessionLocal() as db:
        crud.delete_chain_user_totp(db, chain_user.chain, chain_user.user_id)
        if auth_data is None:
            log.error(
                f"TOTP flow failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return
        db.query(models.ChainUser).filter_by(
            user_id=chain_user.user_id, chain=chain_user.chain
        ).update(
            {
                models.ChainUser.auth_verified_at: datetime.now(),
                models.ChainUser.auth_data: auth_data.json(),
                # we can forget password since a new session requires user interaction for TOTP code anyway
                models.ChainUser.password: None,
            }
        )
        db.commit()


async def extend_auth_session_silently(
    chain_identifier: ChainIdentifier, user_id: UUID
) -> Optional[IBookingAuthData]:
    """
    Performs a cookie-based authentication to extend the auth cookie and retrieve fresh access and refresh tokens.
    No user interaction required, unless the session cookies are missing or expired.
    """
    with SessionLocal() as db:
        chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if chain_user is None:
            log.error(f"'{chain_identifier}' user not found for id '{user_id}'")
            return None
        auth_data_str = chain_user.auth_data
        if auth_data_str is None:
            log.warning(
                f"Auth session not found for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
    log.debug(
        f"Extending auth session for '{chain_user.chain}' user '{chain_user.username}' ..."
    )
    try:
        cookies = IBookingAuthData(**json.loads(auth_data_str)).cookies
    except (json.JSONDecodeError, ValidationError):
        log.error(
            f"Invalid auth data for '{chain_user.chain}' user '{chain_user.username}'"
        )
        return None
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        context = await browser.new_context()
        await playwright_trace_start(context)
        page = await context.new_page()
        await page.goto(SIT_LOGIN_URL)
        refresh_res = await authenticate_with_session_cookies(page, cookies)
        if refresh_res is None:
            log.error(
                f"Refresh token extension failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            await playwright_trace_stop(context, "extend_auth_session_failed")
            return None
        ibooking_token = await get_ibooking_token_from_access_token(
            refresh_res.access_token.token
        )
        if ibooking_token is None:
            log.error(
                f"Ibooking token extraction failed for '{chain_user.chain}' user '{chain_user.username}'"
            )
            await playwright_trace_stop(context, "extend_auth_session_failed")
            return None
        ibooking_valid = await validate_ibooking_token(ibooking_token.token)
        if not ibooking_valid:
            log.error(
                f"Ibooking token is invalid for '{chain_user.chain}' user '{chain_user.username}'"
            )
            await playwright_trace_stop(context, "extend_auth_session_failed")
            return None
        cookies = await extract_cookies_from_url(page, SIT_AUTH_COOKIE_URL)
        await playwright_trace_stop(context, "extend_auth_session")
        await context.close()
    with SessionLocal() as db:
        db_chain_user = crud.get_db_chain_user(db, chain_identifier, user_id)
        if db_chain_user is None:
            log.error(
                f"Chain user not found for '{chain_user.chain}' user '{chain_user.username}'"
            )
            return None
        auth_data = IBookingAuthData(
            access_token=refresh_res.access_token,
            ibooking_token=ibooking_token,
            refresh_token=refresh_res.refresh_token,
            cookies=cookies,
        )
        db_chain_user.auth_data = auth_data.json()
        db.commit()
    log.info(
        f":heavy_check_mark: Auth session extended for '{chain_user.chain}' user '{chain_user.username}' \n"
        f"  (refresh token expires in {humanize.naturaldelta(refresh_res.refresh_token.expires_at - int(time.time()))})"
    )
    return auth_data
