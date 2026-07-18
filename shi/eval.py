class eval:
    """Helper class to build shell commands for environment loading."""

    def __init__(self):
        self.commands = []

    def export(self, key: str, value: str):
        """Export an environment variable."""
        escaped_value = value.replace('"', '\\"')
        self.commands.append(f'export {key}="{escaped_value}"')

    def alias(self, name: str, command: str):
        """Define a shell alias."""
        escaped_command = command.replace("'", "'\\''")
        self.commands.append(f"alias {name}='{escaped_command}'")

    def add_path(self, directory: str, append: bool = False):
        """Add a directory to the PATH environment variable."""
        if append:
            self.commands.append(f'export PATH="$PATH:{directory}"')
        else:
            self.commands.append(f'export PATH="{directory}:$PATH"')

    def source(self, file_path: str):
        """Source a shell script."""
        self.commands.append(f'[ -f "{file_path}" ] && source "{file_path}"')

    def echo(self, message: str):
        """Print a message to the shell during loading."""
        for line in message.splitlines():
            escaped_line = line.replace("'", "'\\''")
            self.commands.append(f"echo '{escaped_line}'")

    def render(self) -> str:
        """Render all commands into a single shell script string."""
        return "\n".join(self.commands)

    def __str__(self) -> str:
        return self.render()
