from shi import cli
import shi.main


@cli
def main(name: str, greeting: str = "Hello", repeat: int = 1):
    """A CLI tool built with shi that greets a user.

    Try running:
      python examples/example_auto_cli.py --name=Alice --greeting=Bonjour --repeat=3
      python examples/example_auto_cli.py ?
    """
    for _ in range(repeat):
        print(f"{greeting}, {name}!")
