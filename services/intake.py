from constants.app import ALLOWED_PRODUCTS, EMAIL_PATTERN

def is_valid_application_form(data) -> bool:
    business_name = (data.get("business_name") or "").strip()
    owner_name = (data.get("owner_name") or "").strip()
    email = (data.get("email") or "").strip()
    product = (data.get("product") or "").strip()
    revenue_raw = (data.get("revenue") or "").strip()

    if not business_name or len(business_name) > 150:
        return False
    if not owner_name or len(owner_name) > 150:
        return False
    if not email or len(email) > 254 or not EMAIL_PATTERN.match(email):
        return False
    if product not in ALLOWED_PRODUCTS:
        return False

    try:
        revenue = float(revenue_raw)
    except ValueError:
        return False

    if revenue <= 0 or revenue > 1_000_000_000:
        return False

    return True
