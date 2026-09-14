import random

FIRST_NAMES = [
    "Arya", "Jon", "Sansa", "Tyrion", "Daenerys", "Bran", "Cersei", "Jaime",
    "Brienne", "Samwell", "Davos", "Melisandre", "Theon", "Yara", "Gendry",
]
LAST_NAMES = [
    "Stark", "Snow", "Lannister", "Targaryen", "Baratheon", "Tarly",
    "Seaworth", "Greyjoy", "Tully", "Mormont", "Clegane",
]


def generate_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_tax_id() -> str:
    """Generates a random tax ID (CPF) with valid check digits."""
    digits = [random.randint(0, 9) for _ in range(9)]
    while len(set(digits)) == 1:
        digits = [random.randint(0, 9) for _ in range(9)]

    digits.append(_cpf_check_digit(digits))
    digits.append(_cpf_check_digit(digits))
    return "".join(str(d) for d in digits)


def _cpf_check_digit(digits: list) -> int:
    weights = range(len(digits) + 1, 1, -1)
    total = sum(digit * weight for digit, weight in zip(digits, weights))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def generate_amount_cents(min_amount_cents: int, max_amount_cents: int) -> int:
    return random.randint(min_amount_cents, max_amount_cents)


def generate_person(min_amount_cents: int, max_amount_cents: int) -> dict:
    return {
        "name": generate_name(),
        "tax_id": generate_tax_id(),
        "amount": generate_amount_cents(min_amount_cents, max_amount_cents),
    }
