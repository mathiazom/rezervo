import datetime
import json
import time
from enum import Enum, auto
from typing import Optional
from uuid import UUID

import humanize
import pytz
import requests
from rich import print
from rich.console import Console
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

from rezervo.database import crud
from rezervo.database.database import SessionLocal
from rezervo.providers.ibooking.auth import IBookingAuthResult
from rezervo.schemas.config.user import ChainIdentifier, ChainUser

# TODO: move to auth.py

WAIT_FOR_TOTP_SECONDS = 1
WAIT_FOR_TOTP_MAX_SECONDS = 60
REFRESH_TOKEN_FREQUENCY_SECONDS = 60

SIT_LOGIN_URL = "https://www.sit.no/profile"
B2C_COOKIE_URL = "https://sitnettprodb2c.b2clogin.com"

error_console = Console(stderr=True, style="bold red")


class SustainTokensError(Enum):
    NO_SESSION = auto()
    INVALID_IBOOKING_TOKEN = auto()


def get_ibooking_token_from_access_token(token: str):
    res = requests.post(
        "https://api.sit.no/api/ibooking/user/login",
        headers={"Content-Type": "application/json", "x-b2c-token": token},
    )
    return res.json()["accessToken"]


def validate_ibooking_token(token: str):
    res = requests.post(
        "https://ibooking.sit.no/webapp/api/User/validateToken",
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-ibooking-token": token,
        },
        data={"token": token},
    )
    if not res.ok:
        return False, None
    expires_string = res.json()["authTokenExpires"]
    expires_at = int(
        datetime.datetime.strptime(expires_string, "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=pytz.timezone("Europe/Oslo"))
        .timestamp()
    )
    return res.ok, expires_at if res.ok else None


def get_tokens_from_refresh_token(token: str):
    res = requests.post(
        f"{B2C_COOKIE_URL}/sitnettprodb2c.onmicrosoft.com/oauth2/v2.0/token?p=b2c_1_si_email"
        f"&client_id=1fd8cf25-b13b-4bbe-a673-809725291c9c"
        f"&grant_type=refresh_token"
        f"&scope=https%3A%2F%2Fsitnettprodb2c.onmicrosoft.com%2F2390d625-e415-4049-a300-3fab18caa9d2%2Fuser_impersonation+offline_access+openid+profile"
        f"&refresh_token={token}"
    )
    return res.json()


def get_refresh_token_lifetime(token: str):
    return int(get_tokens_from_refresh_token(token)["refresh_token_expires_in"])


def extend_refresh_token(driver):
    """
    force a new non-interactive login to extend the refresh token lifetime
    """
    driver.get(SIT_LOGIN_URL)
    time.sleep(5)
    driver.execute_script("window.localStorage.clear();")
    driver.refresh()
    time.sleep(5)

    WebDriverWait(driver, 10).until(
        ec.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[title='Logg inn med e-post']")
        )
    ).click()

    while True:
        local_storage = driver.execute_script("return localStorage;")
        if local_storage is not None:
            for key in local_storage:
                if key.startswith(f"oidc.user:{B2C_COOKIE_URL}"):
                    tokens = json.loads(local_storage[key])
                    print(
                        "[INFO] Refresh token lifetime:",
                        humanize.precisedelta(
                            get_refresh_token_lifetime(tokens["refresh_token"]),
                            minimum_unit="seconds",
                        ),
                    )
                    return tokens["access_token"], tokens["refresh_token"]
        time.sleep(1)


def extract_cookies_from_url(driver, url) -> list[dict]:
    driver.get(url)
    time.sleep(1)  # TODO: check if this is necessary
    cookies = driver.get_cookies()
    driver.back()
    return cookies


def inject_cookies_from_url(driver, url, cookies):
    driver.get(url)
    time.sleep(1)  # TODO: check if this is necessary
    for cookie in cookies:
        driver.add_cookie(cookie)
    driver.back()


def wait_for_totp(chain_identifier: ChainIdentifier, user_id: UUID) -> Optional[str]:
    totp_wait_start = time.time()
    with SessionLocal() as db:
        while (time.time() - totp_wait_start) < WAIT_FOR_TOTP_MAX_SECONDS:
            totp = crud.get_chain_user_totp(db, chain_identifier, user_id)
            print(f"[INFO] TOTP from database: {totp}")
            if totp is not None:
                return totp
            time.sleep(WAIT_FOR_TOTP_SECONDS)
    return None


def login_with_totp(chain_user: ChainUser):
    # TODO remove any existing totp from database
    with SessionLocal() as db:
        crud.delete_chain_user_totp(db, chain_user.chain, chain_user.user_id)
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    print(f"[INFO] Starting Firefox session ({' '.join(firefox_options.arguments)})")
    with webdriver.Firefox(options=firefox_options) as driver:
        print(f"[INFO] driver {driver}")
        print(f"[INFO] Logging in as '{chain_user.username}' ...")
        driver.get(SIT_LOGIN_URL)
        WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[title='Logg inn med e-post']")
            )
        ).click()
        time.sleep(5)
        WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//input[@type='email']"))
        ).send_keys(chain_user.username)
        WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//input[@type='password']"))
        ).send_keys(chain_user.password)
        submit_button = WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", submit_button)
        driver.execute_script("arguments[0].click();", submit_button)
        send_button = WebDriverWait(driver, 30).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, "button[id='sendCode']"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", send_button)
        driver.execute_script("arguments[0].click();", send_button)
        print("[INFO] Waiting for TOTP code from user.")
        totp = wait_for_totp(chain_user.chain, chain_user.user_id)
        if totp is None:
            error_console.print(
                f"[FAILED] TOTP not provided (waited {WAIT_FOR_TOTP_MAX_SECONDS} seconds)."
            )
            return
        if len(totp) != 6 or not totp.isdigit():
            error_console.print(
                "[FAILED] Invalid TOTP code. Please make sure the file contains a 6-digit number."
            )
            return
        WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.XPATH, "//input[@type='text']"))
        ).send_keys(totp)
        verify_button = WebDriverWait(driver, 10).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, "button[id='verifyCode']"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", verify_button)
        driver.execute_script("arguments[0].click();", verify_button)
        time.sleep(5)
        print("[INFO] TOTP verification sent")
        return extract_cookies_from_url(driver, B2C_COOKIE_URL)


def initialize_auth_session_interactively(
    chain_identifier: ChainIdentifier, user_id: UUID
):
    """
    Performs authentication with email, password and TOTP code.
    Requires user interaction to retrieve TOTP code.
    """
    with SessionLocal() as db:
        chain_user = crud.get_chain_user(db, chain_identifier, user_id)
    if chain_user is None:
        error_console.print("[FAILED] ❌ Chain user not found.")
        return
    cookies = login_with_totp(chain_user)
    if cookies is None or len(cookies) == 0:
        error_console.print("[FAILED] ❌ Cookies not found after TOTP verification.")
        return
    with SessionLocal() as db:
        # TODO: add some extra checks to see if actually authorized with totp
        crud.update_chain_user_totp_verified_at(
            db, chain_user.chain, chain_user.user_id
        )
        db_chain_user = crud.get_db_chain_user(db, chain_identifier, user_id)
        if db_chain_user is None:
            error_console.print("[FAILED] ❌ db chain user not found.")
            return
        db_chain_user.auth_token = IBookingAuthResult(cookies=cookies).json()
        db.commit()


def extend_auth_session_silently(
    chain_identifier: ChainIdentifier, user_id: UUID
) -> Optional[SustainTokensError]:
    """
    Performs a cookie-based authentication to extend the auth cookie and retrieve fresh access and refresh tokens.
    No user interaction required, unless the session cookies are missing or expired.
    """
    with SessionLocal() as db:
        chain_user = crud.get_chain_user(db, chain_identifier, user_id)
        if chain_user is None:
            error_console.print("[FAILED] ❌ Chain user not found.")
            return SustainTokensError.NO_SESSION
        token = chain_user.auth_token
        if token is None:
            error_console.print("[FAILED] ❌ Auth session not found.")
            return SustainTokensError.NO_SESSION
    cookies = IBookingAuthResult(**json.loads(token)).cookies
    firefox_options = Options()
    firefox_options.add_argument("-headless")
    print(f"[INFO] Starting Firefox session ({' '.join(firefox_options.arguments)})")
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.get(SIT_LOGIN_URL)
        time.sleep(5)
        print("[INFO] Injecting cookies from previous session ...")
        inject_cookies_from_url(driver, B2C_COOKIE_URL, cookies)
        access_token, refresh_token = extend_refresh_token(driver)
        print(
            "[INFO]   refresh token  :",
            refresh_token[:20] + "..." + refresh_token[-10:],
        )
        print(
            "[INFO]   access token   :", access_token[:20] + "..." + access_token[-10:]
        )
        ibooking_token = get_ibooking_token_from_access_token(access_token)
        print(
            "[INFO]   ibooking token :",
            ibooking_token[:20] + "..." + ibooking_token[-10:],
        )
        ibooking_valid, ibooking_expires_at = validate_ibooking_token(ibooking_token)
        if not ibooking_valid:
            error_console.print("[FAILED] ❌ iBooking token is invalid")
            return SustainTokensError.INVALID_IBOOKING_TOKEN
        print(
            f"[INFO]   ✔ ibooking token is valid "
            f"(for {humanize.precisedelta(ibooking_expires_at - time.time(), minimum_unit='seconds')})"
        )
        cookies = extract_cookies_from_url(driver, B2C_COOKIE_URL)
    with SessionLocal() as db:
        db_chain_user = crud.get_db_chain_user(db, chain_identifier, user_id)
        if db_chain_user is None:
            error_console.print("[FAILED] ❌ db chain user not found.")
            return SustainTokensError.NO_SESSION
        db_chain_user.auth_token = IBookingAuthResult(cookies=cookies).json()
        db.commit()
    return None


def sustain_auth_session_silently(chain_identifier: ChainIdentifier, user_id: UUID):
    start_time = time.time()
    totp_verified_at = None
    print("[INFO] Starting auth session sustainment loop ...")
    print("[INFO]", "\u2500" * 70)
    while True:
        res = extend_auth_session_silently(chain_identifier, user_id)
        if totp_verified_at is None:
            with SessionLocal() as db:
                totp_verified_at = crud.get_chain_user_totp_verified_at(
                    db, chain_identifier, user_id
                )
        if res is not None or totp_verified_at is None:
            error_console.print(f"[FAILED] Auth sustainment aborted: {res}")
            return
        print(
            "[INFO] Sustainment elapsed:",
            humanize.precisedelta(
                int(time.time() - start_time), minimum_unit="seconds"
            ),
        )
        print(
            "[INFO] Session age:",
            humanize.precisedelta(
                datetime.datetime.now() - totp_verified_at, minimum_unit="seconds"
            ),
        )
        print("[INFO]", "\u2500" * 70)
        time.sleep(REFRESH_TOKEN_FREQUENCY_SECONDS)
