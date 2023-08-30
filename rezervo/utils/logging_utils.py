from rich.console import Console

err = Console(stderr=True, style="bold red")
warn = Console(style="yellow")
console = Console()


def stat(message: str, spinner: str = "bouncingBall"):
    return console.status(message, spinner=spinner)
