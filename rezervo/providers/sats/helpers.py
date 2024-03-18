import json
import re

import xxhash


def retrieve_sats_page_props(html_content: str):
    data_pattern = r'<script data-props="true" type="application\/json">(.*?)<\/script>'
    match = re.search(data_pattern, html_content, re.DOTALL)
    if match is None:
        raise Exception("Failed to retrieve Sats page props")
    json_string = str(match.group(1).strip())

    # Fix their bad json escaping
    corrected_json_string = (
        json_string.encode().decode("unicode_escape").encode("latin1").decode()
    )
    return json.loads(corrected_json_string)


def club_name_from_center_name(center_name: str) -> str:
    return center_name.removeprefix("SATS ")


def create_activity_id(activity_name: str, club_name: str) -> str:
    return xxhash.xxh64(f"{activity_name}@{club_name}".strip()).hexdigest()
