"""
category_photos.py
==================
Hand-picked food photos for the Diet dashboard cards. Each photo was checked by eye to match
the card (a buddha bowl for Vegan, grilled chicken for Muscle Building, pasta for Endurance...).

Photos are from Unsplash (https://unsplash.com/license: free to use, no permission needed) and are
loaded from Unsplash's image CDN at a card-sized resolution. If a photo is missing for a category
the dashboard falls back to a matching Food.com recipe photo.
"""

_CDN = "https://images.unsplash.com/photo-{id}?auto=format&fit=crop&w=720&h=440&q=72"

# key -> (Unsplash photo id, alt text)
_PHOTOS = {
    # Dietary preferences
    "vegetarian": ("1567188040759-fb8a883dc6d8", "Paneer tikka with peppers and onions on a sizzling plate"),
    "vegan": ("1512621776951-a57141f2eefd", "Vegan buddha bowl with chickpeas, avocado, tomatoes and greens"),
    "non_vegetarian": ("1565557623262-b51c2513a641", "Butter chicken curry served with naan"),
    "eggetarian": ("1525351484163-7529414344d8", "Fried egg on toasted bread"),
    "balanced": ("1600335895229-6e75511892c8", "Assorted meal-prep bowls with salad, grains and vegetables"),
    # Fitness goals
    "weight_loss": ("1505253716362-afaea1d3d1af", "Spinach salad with berries and seeds"),
    "weight_gain": ("1484723091739-30a097e8f929", "French toast stack with banana and blueberries"),
    "muscle_building": ("1598515214211-89d3c73ae83b", "Grilled chicken breast with mixed vegetables"),
    "high_protein": ("1532550907401-a500c9a57435", "Grilled chicken with lemon and roasted vegetables"),
    "low_carb": ("1529042410759-befb1204b468", "Meatballs on a bed of fresh greens"),
    "endurance": ("1551183053-bf91a1d81141", "Bowl of fettuccine pasta"),
    "recovery": ("1467003909585-2f8a72700288", "Salmon fillet with vegetables"),
    # Sports
    "cricket": ("1585937421612-70a008356fbe", "Indian curries served in copper bowls"),
    "football": ("1555939594-58d7cb561ad1", "Grilled kebabs with roasted potatoes"),
    "basketball": ("1473093295043-cdd812d0e601", "Pasta salad with tomatoes and fresh greens"),
    "tennis": ("1490474418585-ba9bad8fd0ea", "Fresh fruit bowl with yogurt"),
    "badminton": ("1546069901-ba9599a7e63c", "Salad bowl with grilled fish, boiled egg and vegetables"),
    "swimming": ("1519708227418-c8fd9a32b7a2", "Seared salmon fillet with greens"),
    "running": ("1563379926898-05f4575a45d8", "Spaghetti with prawns and tomato"),
    "cycling": ("1609501676725-7186f017a4b7", "Rice bowls with vegetables and toppings"),
    "gym": ("1482049016688-2d3e1b311543", "Boiled eggs with avocado on toast"),
    "bodybuilding": ("1610057099443-fde8c4d50f91", "Grilled chicken with kale salad"),
    "yoga": ("1623428187969-5da2dcea5ebf", "Vegan bowl with avocado, quinoa and vegetables"),
    "other_sport": ("1590301157890-4810ed352733", "Bowl of rice, vegetables and a fried egg"),
}


def category_photo(key: str):
    """{url, alt, credit, credit_url} for a Diet category, or None."""
    hit = _PHOTOS.get(key)
    if not hit:
        return None
    pid, alt = hit
    return {"url": _CDN.format(id=pid), "alt": alt, "credit": "Photo: Unsplash", "source": "unsplash"}
