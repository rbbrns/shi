#!/usr/bin/env python3

import sys
import os
import time
import stat

# --- Utility Functions ---


def get_file_type(mode):
    """Converts st_mode integer into a readable file type string."""
    if stat.S_ISFIFO(mode):
        return "PIPE/FIFO"
    if stat.S_ISCHR(mode):
        return "Character Device (TTY)"
    if stat.S_ISREG(mode):
        return "Regular File"
    if stat.S_ISSOCK(mode):
        return "Socket"
    return "Unknown/Other"


def print_fd_info(fd_number, file_obj):
    """Prints device, inode, and file type information for a given FD."""

    # Use sys.stderr so the output doesn't interfere with the pipe's data stream
    try:
        fd_stats = os.fstat(fd_number)

        is_tty = file_obj.isatty()
        file_type = get_file_type(fd_stats.st_mode)

        print("-" * 50, file=sys.stderr)
        print(
            f"{os.getpid()}: FD {fd_number} ({'stdin' if fd_number == 0 else 'stdout'}):",
            file=sys.stderr,
        )
        print(f"{os.getpid()}:  Is TTY/Terminal:       {is_tty}", file=sys.stderr)
        print(f"{os.getpid()}:  File Type (st_mode):   {file_type}", file=sys.stderr)
        # These are the values we suspect don't match on macOS
        print(
            f"{os.getpid()}:  Device ID (st_dev):    {fd_stats.st_dev}", file=sys.stderr
        )
        print(
            f"{os.getpid()}:  Inode Number (st_ino): {fd_stats.st_ino}", file=sys.stderr
        )
        print("-" * 50, file=sys.stderr)

    except Exception as e:
        print(f"Error accessing FD {fd_number}: {e}", file=sys.stderr)


# --- Main Execution ---


def main():
    # 1. Print metadata for standard input (FD 0) and standard output (FD 1)
    print_fd_info(0, sys.stdin)
    time.sleep(1)
    print_fd_info(1, sys.stdout)
    time.sleep(1)

    # 2. Keep the pipe open

    # If we are the writer (stdout is a pipe), we send a payload.
    # This ensures the pipe stays alive and the reader receives data.
    if not sys.stdout.isatty():
        # NOTE: This data *will* be received by the next process's stdin.
        print(f"{os.getpid()}: Cooperative pipe data payload.", flush=True)

    try:
        # Sleep for one hour (3600 seconds) to allow time for inspection
        time.sleep(3600)
    except KeyboardInterrupt:
        print("\nExiting...", file=sys.stderr)


if __name__ == "__main__":
    main()
