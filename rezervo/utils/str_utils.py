def format_name_list_to_natural(names: list[str]):
    return (
        names[0]
        if len(names) == 1
        else ", ".join(names[:-1]) + f" {'og ' + names[-1] if len(names) > 1 else ''}"
    )
