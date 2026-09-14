from src.common.random_person import generate_person


class UniquePersonGenerator:
    """Generates random people whose tax IDs never repeat within one instance (RF1.2)."""

    def __init__(self, min_amount_cents: int, max_amount_cents: int):
        self._min_amount_cents = min_amount_cents
        self._max_amount_cents = max_amount_cents
        self._seen_tax_ids = set()

    def next(self) -> dict:
        person = generate_person(self._min_amount_cents, self._max_amount_cents)
        while person["tax_id"] in self._seen_tax_ids:
            person = generate_person(self._min_amount_cents, self._max_amount_cents)
        self._seen_tax_ids.add(person["tax_id"])
        return person
