"""
food_labels.py
==============
Ingredient-based food labelling shared by the dataset build script and the running app:
diet classification (via the existing ingredient classifier), "needs verification" notes for
ingredients of uncertain origin, possible allergens, and alcohol detection.
Labels are always derived from ingredients and never from a recipe title.
"""

import re

from backend.app.services.ingredient_classifier import classify_ingredient

ALCOHOL_RE = re.compile(r"\b(wine|beer|vodka|rum|whiske?y|bourbon|brandy|liqueur|tequila|sherry|gin|cognac|"
                        r"kahlua|amaretto|schnapps|vermouth|champagne|sake|mirin|marsala|port wine|ale|stout|lager)\b")

ALLERGEN_PATTERNS = {
    "peanut": re.compile(r"\bpeanuts?\b|\bpeanut butter\b|\bgroundnuts?\b"),
    "tree_nuts": re.compile(r"\b(almonds?|cashews?|walnuts?|pecans?|pistachios?|hazelnuts?|filberts?|macadamias?|"
                            r"brazil nuts?|pine nuts?|pignolis?|praline|marzipan|nutella)\b"),
    "soy": re.compile(r"\b(soy|soya|tofu|tempeh|edamame|miso|tamari|soybeans?|textured vegetable protein|tvp|"
                     r"kecap manis|ketjap manis|teriyaki|hoisin|black bean sauce|natto)\b"),
    "gluten": re.compile(r"\b(wheat|flour|bread|breadcrumbs?|bread crumbs|pasta|spaghetti|macaroni|noodles|couscous|"
                         r"barley|rye|semolina|bulgur|bulghur|seitan|crackers?|tortillas?|pita|naan|roti|chapati|"
                         r"panko|croutons|soy sauce|farro|spelt|orzo|lasagna|penne|fettuccine|linguine|biscuits?|"
                         r"atta|maida|rava|sooji|suji|vermicelli|wonton|dumpling|pie crust|puff pastry|phyllo|filo|"
                         r"kecap manis|ketjap manis|teriyaki|hoisin|hokkien noodles|udon|ramen|soba)\b"),
    "sesame": re.compile(r"\b(sesame|tahini|til)\b"),
    "mustard": re.compile(r"\bmustard\b"),
}
GLUTEN_FREE_FLOUR_RE = re.compile(r"\b(rice|almond|coconut|chickpea|gram|besan|corn|tapioca|potato|buckwheat|"
                                  r"oat|sorghum|millet|ragi|quinoa|cassava|arrowroot|garbanzo)\s+(flour|noodles|pasta|tortillas?|bread)\b"
                                  r"|\bcorn tortillas?\b|\brice (noodles|vermicelli|paper)\b|\bgluten[- ]free\b")

# Ingredients whose animal origin cannot be decided from the name alone.
VERIFY_ALL_VEG = [
    (re.compile(r"\bworcestershire\b"), "Worcestershire sauce usually contains anchovies"),
    (re.compile(r"\bcaesar\b"), "Caesar dressing usually contains anchovies"),
    (re.compile(r"\b(broth|stock|bouillon|consomm[eé]|gravy|drippings)\b"), "broth/stock/gravy of unspecified origin"),
    (re.compile(r"\bmarshmallows?\b"), "marshmallows usually contain gelatin"),
    (re.compile(r"\bjell-?o\b|\bjelly powder\b"), "gelatin dessert"),
    (re.compile(r"\b(dashi|bonito)\b"), "dashi/bonito is fish based"),
    (re.compile(r"\bpesto\b"), "pesto may contain cheese made with animal rennet"),
    (re.compile(r"\bshrimp paste|belacan\b"), "shrimp paste"),
]
VEG_SAFE_STOCK_RE = re.compile(r"\b(vegetable|veggie|vegetarian|vegan|mushroom|no[- ]chicken|plant[- ]based)\b")
VERIFY_VEGAN = [
    (re.compile(r"\bhoney\b"), "honey is an animal product for most vegans"),
    (re.compile(r"\bmargarine\b"), "some margarines contain whey or milk solids"),
    (re.compile(r"\b(milk chocolate|chocolate chips|semi-sweet chocolate|white chocolate)\b"), "chocolate may contain milk"),
    (re.compile(r"\b(cool whip|whipped topping)\b"), "whipped topping contains milk derivatives"),
    (re.compile(r"\b(naan|brioche|croissants?)\b"), "may contain milk, butter or eggs"),
    (re.compile(r"\b(cake mix|pudding mix|biscuit mix|bisquick|pancake mix)\b"), "packaged mixes may contain milk or eggs"),
    (re.compile(r"\bpasta\b.*\begg\b|\begg noodles\b"), "egg pasta"),
]


# Animal products the shared ingredient classifier's keyword lists do not cover. Kept here (rather
# than in dietary_rules.py) so the existing SLM validator behaves exactly as before.
EXTRA_MEAT_RE = re.compile(
    r"\b(sirloin|brisket|chuck (roast|steak)|rib ?eye|t-bone|porterhouse|filet mignon|flank steak|skirt steak|"
    r"short ribs?|spare ?ribs?|baby back ribs?|(pork|beef|lamb|veal) ribs?|meat ?balls?|meat ?loaf|"
    r"hamburgers?(?! buns?)(?! rolls?)|hot ?dogs?(?! buns?)|frankfurters?|wieners?|bratwursts?|kielbasa|andouille|"
    r"mortadella|bologna|liverwurst|livers?|giblets|oxtails?|goat meat|rabbit|cornish (game )?hens?|game hens?|"
    r"\bhens?\b|capon|poussin|squab|elk|wild boar|guanciale|speck|lardons|cracklings|pork rinds|chicharr[oó]n|"
    r"bone broth|sweetbreads|haggis|spam|keema|mince(d)? (meat|beef|lamb|mutton)|ground (meat|round|chuck|sirloin)|"
    r"roast beef|beef|corned|jerky|prosciutto|serrano ham|bresaola|duck|goose|turkey|"
    r"roe|surimi|eel|sole fillets?|perch|walleye|grouper|pollock|carp|monkfish|whitefish|kingfish|pomfret|rohu|"
    r"hilsa|bangda|langoustines?|abalone|conch|snails?|escargots?|frog legs|alligator|krill|kippers?|lox|"
    r"bonito|dashi|shrimp paste|fish paste|fish stock|oyster sauce|anchov(y|ies)|fryers?|stew meat|meat|"
    r"(rump|pot|chuck|round|shoulder|rib|sirloin|top round|bottom round|eye of round|arm|blade|beef|pork|lamb|veal|"
    r"venison|leftover) roasts?|boston butt|pork butt|country(-style)? ribs|franks|hake|orange roughy|bream|pilchards?|"
    r"talapia|seafood|jam[oó]n|moose|caribou|buffalo meat|ground buffalo|bison|chili con carne)\b"
    r"|^roasts?$")
EXTRA_EGG_RE = re.compile(r"\b(meringue|aioli|hollandaise|egg ?nog|mayo)\b")
EXTRA_DAIRY_RE = re.compile(
    r"\b(lassi|kefir|quark|mascarpone|gruy[eè]re|emmentha?l|halloumi|burrata|brie|camembert|gouda|colby|havarti|"
    r"asiago|romano|pecorino|manchego|fontina|velveeta|queso|khoa|khoya|mawa|malai|rabri|chhena|casein|"
    r"dulce de leche|custard|raita|kheer|shrikhand|paneer|panir|cheese|cream|milk|yogh?urt|butter|ghee)\b")
_PLANT_LOOKALIKE_RE = re.compile(
    r"\b(almond|soy|soya|oat|coconut|rice|cashew|hazelnut|hemp|pea|flax|plant[- ]based|vegan|non[- ]dairy|dairy[- ]free|"
    r"peanut|cocoa|cacao|shea|apple|nut|seed|sunflower|tahini|vegetable)\s+(milk|cream|butter|yogh?urt|cheese|mayo|"
    r"mayonnaise|creamer)s?\b|\bcream of tartar\b|\bbutternut\b|\bbutter beans?\b|\bbutterhead\b|"
    r"\bmilk thistle\b|\bcoconut cream\b|\bcream of (coconut|rice|wheat)\b|\bice cream cones?\b|"
    r"\bmeatless\b|\bimitation (meat|chicken|beef)\b|\bveggie (burger|crumbles|sausage)s?\b|"
    r"\b(plant|soy|vegan|vegetarian)[- ](based )?(burger|sausage|chicken|crumbles)s?\b|\bbeefsteak tomato(es)?\b"
    r"|\b(coconut|nut|walnut|pecan|almond|cashew) meats?\b|\bmeat tenderi[sz]er\b")


# Food.com metadata tags / categories that name the main animal ingredient
META_MEAT_TAGS = {
    "meat", "poultry", "chicken", "beef", "seafood", "pork", "chicken-breasts", "ground-beef", "fish", "shellfish",
    "saltwater-fish", "shrimp", "turkey", "salmon", "pork-sausage", "bacon", "ham", "chicken-thighs-legs", "tuna",
    "lamb-sheep", "crab", "roast-beef", "pork-loins", "roast", "steaks", "whole-chicken", "steak", "freshwater-fish",
    "scallops", "wild-game", "pork-ribs", "cod", "beef-sausage", "veal", "clams", "tilapia", "halibut", "turkey-breasts",
    "deer", "beef-ribs", "sole-and-flounder", "mussels", "lobster", "whole-turkey", "catfish", "oysters", "duck",
    "beef-organ-meats", "trout", "meatloaf", "mahi-mahi", "meatballs", "crawfish", "beef-liver", "squid",
    "chicken-livers", "bass", "orange-roughy", "whitefish", "rabbit", "turkey-burgers", "duck-breasts", "pheasant",
    "whole-duck", "elk", "perch", "moose", "goose", "quail", "octopus", "pickeral", "bear", "beef-kidney",
    "main-dish-pork", "main-dish-beef", "main-dish-chicken", "lamb-sheep-main-dish", "stews-poultry",
    "main-dish-seafood", "shrimp-main-dish", "pork-crock-pot", "beef-crock-pot", "chicken-crock-pot", "chicken-stews",
    "chicken-stew", "roast-beef-main-dish", "roast-beef-comfort-food", "pork-loins-roast", "pork-loin", "pot-roast",
    "ham-and-bean-soup", "beef-barley-soup", "beef-sauces",
}
META_MEAT_CATEGORIES = {
    "Chicken", "Meat", "Pork", "Poultry", "Steak", "Lamb/Sheep", "Chicken Breast", "Chicken Thigh & Leg", "Whole Chicken",
    "Roast Beef", "Ham", "Pork Chops", "Pork Loin", "Duck", "Deer", "Veal", "Crawfish", "Shrimp", "Scallop", "Squid",
    "Tuna", "Salmon", "Tilapia", "Halibut", "Catfish", "Trout", "Bass", "Crab", "Lobster", "Mussels", "Chicken Livers",
    "Meatloaf", "Meatballs", "Turkey Breasts", "Wild Game", "Whitefish", "Perch", "Orange Roughy", "Mahi Mahi", "Octopus",
    "Duck Breasts", "Goose", "Elk", "Moose", "Pheasant", "Quail", "Rabbit", "Squab", "Beef Organ Meats",
    "Pork Organ Meats", "Lamb Organ Meats", "Oysters", "Clams", "Bear", "Whole Turkey", "Whole Duck", "Sole/Flounder",
}
TITLE_MEAT_RE = re.compile(
    r"\b(chicken|beef|pork|lamb|mutton|fish|shrimp|prawns?|salmon|tuna|bacon|ham|turkey|steak|sausages?|crab|meat|"
    r"venison|moose|cod|tilapia|halibut|lobster|scallops?|clams?|mussels?|keema|ribs|wings|drumsticks?|brisket|veal|"
    r"duck|goose|pepperoni|salami|chorizo|anchov\w+|sardines?|oysters?|squid|calamari|octopus|gyros?|meatballs?|"
    r"hot dogs?|bratwurst|jerky)\b", re.I)
TITLE_NEGATION_RE = re.compile(
    r"\b(vegan|vegetarian|veggie|tofu|meatless|faux|mock|no[- ]meat|seitan|tempeh|style|flavou?red|portobello|"
    r"portabella|mushroom|lentil|bean|eggplant|cauliflower|soy|tvp|quorn|imitation|for|free|not|like|better|fries|"
    r"seasoning|sauce|marinade|rub|dressing|dip|batter|buns?|stuffing|salt|scallop(ed)? potatoes|lettuce)\b", re.I)


def metadata_says_meat(tags, category) -> bool:
    return bool(set(tags or []) & META_MEAT_TAGS) or (category or "") in META_MEAT_CATEGORIES


def title_meat_warning(title: str):
    if TITLE_MEAT_RE.search(title or "") and not TITLE_NEGATION_RE.search(title or ""):
        return {"ingredient": title, "reason": "the recipe title mentions meat or fish that is not in the listed "
                                               "ingredients; the ingredient list may be incomplete",
                "applies_to": ["vegan", "vegetarian", "eggitarian"]}
    return None


def extra_animal_flags(name: str):
    low = _PLANT_LOOKALIKE_RE.sub(" ", (name or "").lower())
    return {"meat": bool(EXTRA_MEAT_RE.search(low)), "egg": bool(EXTRA_EGG_RE.search(low)),
            "dairy": bool(EXTRA_DAIRY_RE.search(low))}


def classify_diet(ingredient_names):
    has_meat = has_egg = has_dairy = False
    for ing in ingredient_names:
        c = classify_ingredient(ing)
        x = extra_animal_flags(ing)
        if c["is_meat"] or c["is_poultry"] or c["is_fish"] or c["is_seafood"] or x["meat"]:
            has_meat = True
        if c["is_egg"] or x["egg"]:
            has_egg = True
        if c["is_dairy"] or x["dairy"]:
            has_dairy = True
    if has_meat:
        diet = "non_vegetarian"
    elif has_egg:
        diet = "eggitarian"
    elif has_dairy:
        diet = "vegetarian"
    else:
        diet = "vegan"
    return diet, {"meat_or_fish": has_meat, "egg": has_egg, "dairy": has_dairy}


def diet_verification(ingredient_names, diet):
    """Returns ingredients that make the diet label uncertain (for the stricter diets)."""
    notes = []
    if diet == "non_vegetarian":
        return notes
    for ing in ingredient_names:
        low = ing.lower()
        for pat, reason in VERIFY_ALL_VEG:
            if pat.search(low):
                if "broth" in reason and VEG_SAFE_STOCK_RE.search(low):
                    continue
                notes.append({"ingredient": ing, "reason": reason, "applies_to": ["vegan", "vegetarian", "eggitarian"]})
                break
        if diet == "vegan":
            for pat, reason in VERIFY_VEGAN:
                if pat.search(low):
                    notes.append({"ingredient": ing, "reason": reason, "applies_to": ["vegan"]})
                    break
    return notes


def detect_allergens(ingredient_names, flags):
    found = set()
    if flags.get("dairy"):
        found.add("dairy")
    if flags.get("egg"):
        found.add("egg")
    for ing in ingredient_names:
        low = ing.lower()
        c = classify_ingredient(low)
        if c["is_fish"]:
            found.add("fish")
        if c["is_seafood"]:
            found.add("shellfish")
        for key, pat in ALLERGEN_PATTERNS.items():
            if not pat.search(low):
                continue
            if key == "gluten" and GLUTEN_FREE_FLOUR_RE.search(low):
                continue
            if key == "peanut" and "peanut oil" in low:
                pass  # refined peanut oil is still listed: allergy decisions belong to the user
            found.add(key)
    return sorted(found)


