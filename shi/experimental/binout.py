from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import box
from rich.console import Group
from typing import Dict, Tuple, Optional, Union, Any
import math


def binout(
    value: int,
    bits: int = 32,
    endian: str = "big",
    fields: Optional[
        Dict[str, Union[Tuple[int, int], Tuple[int, int, str], slice]]
    ] = None,
):
    """
    Displays a number in human-friendly formats: Decimal, Hex, Binary, and ASCII.
    Also provides a bit-level visualization and field analysis.

    Args:
        value: The integer value to display.
        bits: The number of bits to display (default 32, max 1024).
        endian: 'big' or 'little' endian for byte interpretation (default 'big').
        fields: Dictionary mapping field names to:
                - (start_bit, length)
                - (start_bit, length, color)
                - slice(start, stop) -> bits [start, stop)
                start_bit is 0-indexed from the LSB.
    """
    console = Console()

    if bits > 1024:
        console.print(
            f"[bold red]Error:[/bold red] bits ({bits}) exceeds maximum of 1024."
        )
        return

    # Ensure value fits in the specified number of bits
    mask = (1 << bits) - 1
    masked_value = value & mask
    inverse_value = masked_value ^ mask

    # --- Value Analysis Panel ---

    # Formats
    dec_str = f"{value}"
    hex_str = f"0x{masked_value:0{math.ceil(bits / 4)}X}"
    bin_str = f"{masked_value:0{bits}b}"

    # Inverse Formats
    inv_dec_str = f"{inverse_value}"
    inv_hex_str = f"0x{inverse_value:0{math.ceil(bits / 4)}X}"
    inv_bin_str = f"{inverse_value:0{bits}b}"

    # Group binary string for readability (groups of 8 for better byte alignment)
    grouped_bin = " ".join([bin_str[i : i + 8] for i in range(0, len(bin_str), 8)])
    inv_grouped_bin = " ".join(
        [inv_bin_str[i : i + 8] for i in range(0, len(inv_bin_str), 8)]
    )

    # ASCII representation
    # Convert to bytes
    num_bytes = math.ceil(bits / 8)
    try:
        byte_val = masked_value.to_bytes(num_bytes, byteorder=endian, signed=False)
    except OverflowError:
        byte_val = b"\x00" * num_bytes

    ascii_chars = []
    for b in byte_val:
        if 32 <= b <= 126:
            ascii_chars.append(chr(b))
        else:
            ascii_chars.append(".")  # Placeholder for non-printable
    ascii_str = "".join(ascii_chars)

    # Wrap ASCII string if it's long (e.g. > 64 chars)
    if len(ascii_str) > 64:
        # Split into chunks of 64
        ascii_chunks = [ascii_str[i : i + 64] for i in range(0, len(ascii_str), 64)]
        ascii_display = "\n".join(ascii_chunks)
    else:
        ascii_display = ascii_str

    # Create main info table
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold cyan", justify="right")
    grid.add_column(style="yellow")

    grid.add_row("Decimal:", dec_str)
    grid.add_row("Hex:", hex_str)
    grid.add_row("Binary:", grouped_bin)
    grid.add_row(f"ASCII ({endian}):", ascii_display)
    grid.add_row("Inverse (Hex):", inv_hex_str, style="dim")

    console.print(
        Panel(grid, title=f"Value Analysis: {value}", expand=False, border_style="blue")
    )

    # --- Combined Field Analysis and Bit Visualization ---

    renderables = []

    # Field Analysis Table
    if fields:
        field_table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold magenta",
            expand=True,
        )
        field_table.add_column("Field")
        field_table.add_column("Range")
        field_table.add_column("Value (Dec)")
        field_table.add_column("Value (Hex)")
        field_table.add_column("Value (Bin)")

        for name, spec in fields.items():
            start, length = 0, 0
            color = "cyan"

            if isinstance(spec, slice):
                start = spec.start if spec.start is not None else 0
                stop = spec.stop if spec.stop is not None else bits
                length = stop - start
            elif isinstance(spec, tuple):
                start = spec[0]
                length = spec[1]
                if len(spec) > 2:
                    color = spec[2]

            if length > 0:
                # Extract field value
                field_mask = (1 << length) - 1
                field_val = (masked_value >> start) & field_mask

                field_table.add_row(
                    f"[{color}]{name}[/{color}]",
                    f"{start}:{start+length} ({length})",
                    str(field_val),
                    f"0x{field_val:X}",
                    f"{field_val:0{length}b}",
                )

        renderables.append(field_table)
        renderables.append(Text("\n"))  # Spacer

    # Bit Visualization

    # Responsive grid layout
    # Limit to 32 bits per row to avoid terminal wrapping issues
    bits_per_row = 32

    # Calculate number of rows needed
    num_rows = math.ceil(bits / bits_per_row)

    # Create a container table for the rows
    container_table = Table.grid(padding=(0, 0))

    for row_idx in range(num_rows):
        # Determine range for this row
        row_end_bit = bits - (row_idx * bits_per_row) - 1
        row_start_bit = max(0, row_end_bit - bits_per_row + 1)

        # Create a table for this row of bits
        # Use expand=False to prevent it from taking full width if not needed
        row_table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 0),
            collapse_padding=True,
            expand=False,
        )

        # Columns
        for _ in range(row_end_bit - row_start_bit + 1):
            row_table.add_column(justify="center", width=4)

        # Indices
        indices = []
        for i in range(row_end_bit, row_start_bit - 1, -1):
            indices.append(str(i))
        row_table.add_row(*indices, style="dim")

        # Values
        values = []
        for i in range(row_end_bit, row_start_bit - 1, -1):
            bit_val = (masked_value >> i) & 1

            # Default style
            # Highlight set bits
            if bit_val:
                style = "bold green"
            else:
                style = "dim white"

            # Check if this bit belongs to a field
            if fields:
                for name, spec in fields.items():
                    f_start, f_len = 0, 0
                    f_color = "cyan"

                    if isinstance(spec, slice):
                        f_start = spec.start if spec.start is not None else 0
                        stop = spec.stop if spec.stop is not None else bits
                        f_len = stop - f_start
                    elif isinstance(spec, tuple):
                        f_start = spec[0]
                        f_len = spec[1]
                        if len(spec) > 2:
                            f_color = spec[2]

                    if f_start <= i < f_start + f_len:
                        # If bit is set, use bold field color
                        # If bit is unset, use dim field color or just dim
                        if bit_val:
                            style = f"bold {f_color}"
                        else:
                            style = f"dim {f_color}"
                        break

            values.append(Text(str(bit_val), style=style))
        row_table.add_row(*values)

        container_table.add_row(row_table)

    renderables.append(container_table)

    console.print(
        Panel(
            Group(*renderables),
            title="Bit & Field Visualization",
            expand=False,
            border_style="green",
        )
    )


if __name__ == "__main__":
    # Simple test
    binout(0x12345678, bits=32, fields={"High": slice(16, 32), "Low": slice(0, 16)})
