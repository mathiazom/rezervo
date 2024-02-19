import json
import re


def retrive_sats_page_props(html_content: str):
    data_pattern = r'<script data-props="true" type="application/json">(.*?)<\/script>'
    match = re.search(data_pattern, html_content, re.DOTALL)
    if match is None:
        raise Exception("Failed to retrive Sats page props")
    json_string = str(match.group(1).strip())

    # Fix their bad json escaping
    corrected_json_string = (
        json_string.encode().decode("unicode_escape").encode("latin1").decode()
    )
    return json.loads(corrected_json_string)
