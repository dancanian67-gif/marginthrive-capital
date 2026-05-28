from constants.app import ALLOWED_PRODUCTS, EMAIL_PATTERN, KENYAN_PHONE_PATTERN

def is_valid_application_form(data) -> bool:
    business_name = (data.get("business_name") or "").strip()
    owner_name = (data.get("owner_name") or "").strip()
    email = (data.get("email") or "").strip()
    product = (data.get("product") or "").strip()
    phone_number = (data.get("phone_number") or "").strip().replace(" ", "")
    revenue_raw = (data.get("revenue") or "").strip()
    legal_consent = data.get("legal_consent") == "on" or data.get("privacy_consent") == "on"

    if not business_name or len(business_name) > 150:
        return False
    if not owner_name or len(owner_name) > 150:
        return False
    if email:
        if len(email) > 254 or not EMAIL_PATTERN.match(email):
            return False
    if not phone_number or len(phone_number) > 20 or not KENYAN_PHONE_PATTERN.match(phone_number):
        return False
    if product not in ALLOWED_PRODUCTS:
        return False

    try:
        revenue = float(revenue_raw)
    except ValueError:
        return False

    if revenue <= 0 or revenue > 1_000_000_000:
        return False
    if not legal_consent:
        return False

    return True
