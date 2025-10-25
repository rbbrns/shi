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

To run the restaurant management example, you will use the `cli.py` utility.

1.  **Ensure your virtual environment is activated.**
2.  **Run commands using `python shi/cli.py <command> [args...]`:**

    *   **Take an order:**
        ```bash
        python shi/cli.py take_order John 5 "Pasta Carbonara" 2 special_requests="Extra cheese"
        ```

    *   **Generate a bill:**
        ```bash
        python shi/cli.py generate_bill Alice 10 '[{"menu_item": "Steak", "quantity": 1, "base_price": 30.00}, {"menu_item": "Wine", "quantity": 2, "base_price": 10.00}]'
        ```

    *   **Generate a bill with custom tax rate:**
        ```bash
        python shi/cli.py generate_bill Bob 3 '[{"menu_item": "Pizza", "quantity": 1, "base_price": 15.00}]' TAX_RATE=0.05
        ```

This example showcases a more realistic use case of `@arrg` in a simulated restaurant management service, demonstrating argument resolution across multiple nested functions and overriding default values, now exposed via a command-line interface.
