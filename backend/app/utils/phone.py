from __future__ import annotations

import re

PHONE_NORMALIZATION_RE = re.compile(r"\D+")


def normalize_phone_number(phone: str) -> str:
    """
    Приводит телефон к формату `7XXXXXXXXXX`.

    Удаляет все нецифровые символы, заменяет ведущую 8 на 7 и добавляет 7,
    если переданы 10 цифр.
    """
    digits = PHONE_NORMALIZATION_RE.sub("", phone)
    if not digits:
        return phone
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return digits
    return digits
