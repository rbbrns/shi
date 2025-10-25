from shi.arrg import arrg

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

@arrg
def take_order(customer_name, table_number, menu_item, quantity, special_requests=None):
    """Takes a customer's order."""
    info = get_customer_info() # Resolves customer_name, table_number from parent context
    print(f"Taking order for {info['customer_name']} at Table {info['table_number']}:")
    print(f"  Item: {menu_item}, Quantity: {quantity}")
    if special_requests:
        print(f"  Special Requests: {special_requests}")
    return {"menu_item": menu_item, "quantity": quantity, "special_requests": special_requests}

@arrg
def prepare_dish(menu_item, quantity, chef_name="Chef Gordon"):
    """Simulates preparing a dish."""
    print(f"Preparing {quantity}x {menu_item} by {chef_name}...")
    return f"Prepared {quantity}x {menu_item}"

@arrg
def calculate_item_price(menu_item, quantity, base_price, TAX_RATE, SERVICE_CHARGE_RATE):
    """Calculates the price for a single menu item including tax and service charge."""
    item_total = base_price * quantity
    tax_amount = item_total * TAX_RATE
    service_charge_amount = item_total * SERVICE_CHARGE_RATE
    final_price = item_total + tax_amount + service_charge_amount
    print(f"  {menu_item} ({quantity}x): Base ${base_price:.2f}, Total (incl. tax/service) ${final_price:.2f}")
    return final_price

@arrg
def generate_bill(customer_name, table_number, items_ordered, TAX_RATE, SERVICE_CHARGE_RATE):
    """Generates a bill for the customer."""
    print(f"\n--- Bill for {customer_name} at Table {table_number} ---")
    total_amount = 0
    for item in items_ordered:
        # calculate_item_price will resolve TAX_RATE and SERVICE_CHARGE_RATE from this function's context
        total_amount += calculate_item_price(**item)
    
    print(f"Total: ${total_amount:.2f}")
    print(f"Thank you for dining at {RESTAURANT_NAME}!")
    return total_amount

if __name__ == "__main__":
    print("--- Scenario 1: Basic Order and Bill ---")
    customer_name = "Alice"
    table_number = 5
    
    # take_order will resolve customer_name and table_number from local scope
    order1 = take_order(menu_item="Pasta Carbonara", quantity=2)
    prepare_dish(**order1)

    order2 = take_order(menu_item="Caesar Salad", quantity=1, special_requests="No croutons")
    prepare_dish(**order2, chef_name="Chef Julia")

    items = [
        {"menu_item": "Pasta Carbonara", "quantity": 2, "base_price": 15.50},
        {"menu_item": "Caesar Salad", "quantity": 1, "base_price": 9.00}
    ]
    
    # generate_bill will resolve customer_name, table_number, TAX_RATE, SERVICE_CHARGE_RATE
    # calculate_item_price (called inside generate_bill) will resolve TAX_RATE, SERVICE_CHARGE_RATE from generate_bill's context
    generate_bill(items_ordered=items)

    print("\n--- Scenario 2: Different Tax Rate for a Special Event ---")
    # Override global TAX_RATE for this specific bill generation
    event_tax_rate = 0.05
    customer_name = "Bob"
    table_number = 12
    items_event = [
        {"menu_item": "Steak Frites", "quantity": 1, "base_price": 25.00},
        {"menu_item": "Glass of Wine", "quantity": 2, "base_price": 8.00}
    ]
    generate_bill(items_ordered=items_event, TAX_RATE=event_tax_rate)

    print("\n--- Scenario 3: Custom Service Charge ---")
    customer_name = "Charlie"
    table_number = 3
    custom_service_charge = 0.15
    items_custom = [
        {"menu_item": "Pizza Margherita", "quantity": 1, "base_price": 12.00}
    ]
    # Here, SERVICE_CHARGE_RATE is passed directly to generate_bill, overriding the global
    generate_bill(items_ordered=items_custom, SERVICE_CHARGE_RATE=custom_service_charge)
