from shi.arrg import arrg
from shi.cli import cli, run_cli # New import
import json # New import for JSON parsing

# Global settings for the restaurant
TAX_RATE = 0.08  # 8% sales tax
SERVICE_CHARGE_RATE = 0.10 # 10% service charge
RESTAURANT_NAME = "The Cozy Corner Bistro"

@arrg
def get_customer_info(customer_name, table_number):
    """Retrieves basic customer and table information."""
    print(f"--- {RESTAURANT_NAME} ---")
    print(f"Customer: {customer_name}, Table: {table_number}")
    return {"customer_name": customer_name, "table_number": table_number}

@cli # Decorate with @cli
@arrg
def take_order(customer_name: str, table_number: int, menu_item: str, quantity: int, special_requests: str = None):
    """
    Takes a customer's order.
    Example CLI call: python restaurant_example.py take_order Alice 5 "Pasta Carbonara" 2
    Example CLI call with special requests: python restaurant_example.py take_order Bob 12 "Caesar Salad" 1 special_requests="No croutons"
    """
    info = get_customer_info() # Resolves customer_name, table_number from parent context
    print(f"Taking order for {info['customer_name']} at Table {info['table_number']}:")
    print(f"  Item: {menu_item}, Quantity: {quantity}")
    if special_requests:
        print(f"  Special Requests: {special_requests}")
    return {"menu_item": menu_item, "quantity": quantity, "special_requests": special_requests, "customer_name": customer_name, "table_number": table_number}

@arrg
def prepare_dish(menu_item, quantity, chef_name="Chef Gordon"):
    """
    Simulates preparing a dish.
    This is an internal function, not exposed directly via CLI.
    """
    print(f"Preparing {quantity}x {menu_item} by {chef_name}...")
    return f"Prepared {quantity}x {menu_item}"

@arrg
def calculate_item_price(menu_item, quantity, base_price, TAX_RATE, SERVICE_CHARGE_RATE):
    """
    Calculates the price for a single menu item including tax and service charge.
    This is an internal function, not exposed directly via CLI.
    """
    item_total = base_price * quantity
    tax_amount = item_total * TAX_RATE
    service_charge_amount = item_total * SERVICE_CHARGE_RATE
    final_price = item_total + tax_amount + service_charge_amount
    print(f"  {menu_item} ({quantity}x): Base ${base_price:.2f}, Total (incl. tax/service) ${final_price:.2f}")
    return final_price

@cli # Decorate with @cli
@arrg
def generate_bill(customer_name: str, table_number: int, items_ordered_json: str, TAX_RATE: float = None, SERVICE_CHARGE_RATE: float = None):
    """
    Generates a bill for the customer.
    items_ordered_json should be a JSON string representing a list of item dictionaries.
    Example CLI call: python restaurant_example.py generate_bill Alice 5 '[{"menu_item": "Pasta Carbonara", "quantity": 2, "base_price": 15.50}]'
    """
    items_ordered = json.loads(items_ordered_json) # Parse JSON string

    print(f"\n--- Bill for {customer_name} at Table {table_number} ---")
    total_amount = 0
    for item in items_ordered:
        # calculate_item_price will resolve TAX_RATE and SERVICE_CHARGE_RATE from this function's context
        total_amount += calculate_item_price(**item)
    
    print(f"Total: ${total_amount:.2f}")
    print(f"Thank you for dining at {RESTAURANT_NAME}!")
    return total_amount

if __name__ == "__main__":
    run_cli() # Call run_cli to dispatch commands
