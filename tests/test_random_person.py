from src.common import random_person


def _is_valid_cpf(cpf: str) -> bool:
    digits = [int(c) for c in cpf]
    for check_index in (9, 10):
        weights = range(check_index + 1, 1, -1)
        total = sum(digit * weight for digit, weight in zip(digits[:check_index], weights))
        remainder = (total * 10) % 11
        expected = 0 if remainder == 10 else remainder
        if digits[check_index] != expected:
            return False
    return True


def test_generate_tax_id_has_eleven_digits():
    tax_id = random_person.generate_tax_id()
    assert len(tax_id) == 11
    assert tax_id.isdigit()


def test_generate_tax_id_produces_valid_check_digits():
    for _ in range(200):
        assert _is_valid_cpf(random_person.generate_tax_id())


def test_generate_tax_id_never_repeats_all_digits():
    for _ in range(200):
        tax_id = random_person.generate_tax_id()
        assert len(set(tax_id[:9])) > 1


def test_generate_name_combines_first_and_last_name():
    name = random_person.generate_name()
    first, last = name.split(" ")
    assert first in random_person.FIRST_NAMES
    assert last in random_person.LAST_NAMES


def test_generate_amount_cents_within_range():
    for _ in range(50):
        amount = random_person.generate_amount_cents(1000, 2000)
        assert 1000 <= amount <= 2000


def test_generate_person_has_expected_shape():
    person = random_person.generate_person(1000, 2000)
    assert set(person.keys()) == {"name", "tax_id", "amount"}
    assert 1000 <= person["amount"] <= 2000
