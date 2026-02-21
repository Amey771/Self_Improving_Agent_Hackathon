"""
sample_service.py - A demo service with intentional bugs for the Fix Agent to repair.
"""

import logging

logger = logging.getLogger(__name__)


def calculate_discount(price: float, discount_pct: float) -> float:
    """Return the discounted price. discount_pct should be 0-100."""
    # BUG: division by zero when discount_pct == 100
    return price * (discount_pct / (100 - discount_pct))


def process_payment(amount: float, currency: str = "USD") -> dict:
    """Process a payment and return a result dict."""
    if amount <= 0:
        raise ValueError(f"Amount must be positive, got {amount}")

    # Simulate processing
    logger.info("Processing payment of %s %s", amount, currency)
    return {"status": "success", "amount": amount, "currency": currency}


def get_user_profile(user_id: int) -> dict:
    """Fetch a user profile by ID."""
    if not isinstance(user_id, int):
        raise TypeError(f"user_id must be int, got {type(user_id).__name__}")

    # Simulated DB lookup
    return {"id": user_id, "name": f"User_{user_id}", "active": True}
