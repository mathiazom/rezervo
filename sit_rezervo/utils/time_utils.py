def readable_seconds(s: float):
    minutes = int(s / 60)
    seconds = int(s % 60)
    return "".join([
        f"{minutes} minute{'s' if minutes > 1 else ''}{' and ' if seconds > 0 else ''}" if minutes > 0 else "",
        f"{seconds} second{'s' if seconds > 1 else ''}" if seconds > 0 else ""
    ])
