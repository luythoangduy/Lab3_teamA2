SCENARIOS = [
    {
        "id": 1,
        "name": "Hallucination trap",
        "query": "What is the price and stock of the Samsung Galaxy S24 in our catalog?",
        "expect": "Product not in dummyjson catalog; agent should search and report not found.",
        "tags": ["hallucination"],
    },
    {
        "id": 2,
        "name": "Multi-step (cheapest + stock)",
        "query": "What is the cheapest product in the beauty category and how many units are in stock?",
        "expect": "Agent calls cheapest_in_category(beauty); chatbots may guess.",
        "tags": ["multi-step"],
    },
    {
        "id": 3,
        "name": "Exact lookup by id",
        "query": "Give me the title, price, and brand for product id 7.",
        "expect": "Agent calls get_product_by_id(7) → Chanel Coco Noir.",
        "tags": ["factual"],
    },
    {
        "id": 4,
        "name": "Search + compare",
        "query": "Find mascara products and tell me which one has the lowest price.",
        "expect": "Agent uses search_products(mascara) then compares prices.",
        "tags": ["multi-step"],
    },
]
