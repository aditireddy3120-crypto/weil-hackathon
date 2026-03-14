import random

SUPPLIERS = [
    {"name": "AliExpress", "base_price": 7.5, "shipping": 3},
    {"name": "Amazon", "base_price": 9, "shipping": 1},
    {"name": "LocalVendor", "base_price": 8, "shipping": 2},
]

def select_supplier(cart):

    offers = []

    for supplier in SUPPLIERS:

        # simulate price variation
        price = supplier["base_price"] + random.uniform(-1, 2)

        offers.append({
            "name": supplier["name"],
            "price": round(price, 2),
            "shipping": supplier["shipping"]
        })

    # choose supplier with lowest total cost
    best = min(offers, key=lambda x: x["price"] + x["shipping"])

    return best