"""
Billing module for payment processing.
Simulated production-like code.
"""


class BillingCalculator:

    def __init__(self, tax_rate=0.08):
        self.tax_rate = tax_rate

    def apply_tax(self, amount):
        return amount + (amount * self.tax_rate)

    def apply_discount(self, amount, discount_percent):
        if discount_percent < 0:
            raise ValueError("Discount cannot be negative")
        return amount - (amount * discount_percent / 100)

    def calculate_total(self, amount, discount_percent, installments):
        """
        Calculates total billing amount after discount and tax.
        Splits into installments.
        """
        discounted = self.apply_discount(amount, discount_percent)
        taxed = self.apply_tax(discounted)

        # Simulated logging
        print("Calculating installment amount...")

        # -------------------------------
        # Critical section
        # -------------------------------

        if installments == 0:
            raise ValueError("Installments cannot be zero")

        per_installment = taxed / installments

        return round(per_installment, 2)


def process_payment(amount, discount_percent, installments):
    calculator = BillingCalculator()
    total = calculator.calculate_total(amount, discount_percent, installments)

    if total <= 0:
        raise ValueError("Invalid billing total")

    return {
        "status": "success",
        "installment_amount": total
    }


if __name__ == "__main__":
    # Simulated faulty call
    print(process_payment(1000, 10, 0))