# Examples for shi.arrg

This directory contains example usage of the `shi.arrg` decorator.

## Setup

1.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  **Install the `shi` package:**
    ```bash
    pip install -e ../
    ```
    (This installs the `shi` package from the parent directory in editable mode.)

## Running the Example

1.  **Ensure your virtual environment is activated.**
2.  **Run the example script:**
    ```bash
    python example_arrg.py
    ```

This script demonstrates how `shi.arrg` resolves function arguments from various scopes, including global variables, explicit arguments, and caller's local scope.

## Restaurant Management Example

To run the restaurant management example:

1.  **Ensure your virtual environment is activated.**
2.  **Run the example script:**
    ```bash
    python restaurant_example.py
    ```

This example showcases a more realistic use case of `@arrg` in a simulated restaurant management service, demonstrating argument resolution across multiple nested functions and overriding default values.
