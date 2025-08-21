import re


def format_name_list_to_natural(names: list[str]):
    return (
        names[0]
        if len(names) == 1
        else ", ".join(names[:-1]) + f" {'og ' + names[-1] if len(names) > 1 else ''}"
    )


def standardize_activity_name(raw: str) -> str:
    s = re.sub(r"\s\(\d+\)$", "", raw)
    s = re.sub(r"^\s*-\s*", "", s)
    s = re.sub(r"//+", " ", s).strip()
    return s.title()
