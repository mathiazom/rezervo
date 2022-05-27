import re
from typing import Optional

import requests
from requests import Session

from consts import AUTH_URL, BOOKING_URL, TOKEN_VALIDATION_URL

USER_AGENT = "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"


def authenticate(email: str, password: str) -> Optional[str]:
    session = Session()
    user_agent_header = {'User-Agent': USER_AGENT}
    session.post(AUTH_URL, {
        "name": email,
        "pass": password,
        "form_id": "user_login"
    }, headers=user_agent_header)
    booking_res = session.get(BOOKING_URL, headers=user_agent_header)
    booking_soup = re.sub(" +", " ", booking_res.text.replace("\n", ""))
    cdata_token_matches = re.search(r"<!\[CDATA\[.*?iBookingPreload\(.*?token:.*?\"(.+?)\".*?]]>", booking_soup)
    if cdata_token_matches is None:
        print("[ERROR] Failed to extract authentication token!")
        return None
    try:
        token = cdata_token_matches.group(1)
    except IndexError:
        print("[ERROR] Failed to extract authentication token!")
        return None
    # Validate token
    token_validation = session.post(TOKEN_VALIDATION_URL, {"token": token})
    if token_validation.status_code != requests.codes.OK:
        print("[ERROR] Validation of authentication token failed")
        return None
    token_info = token_validation.json()
    if 'info' in token_info and token_info['info'] == "client-readonly":
        print("[ERROR] Authentication failed, only acquired readonly access")
        return None
    print(f"[INFO] Authentication done.")
    return token
