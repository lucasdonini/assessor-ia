import math
import re
from decimal import Decimal, InvalidOperation

FOREIGN = re.compile(
    r"(?i)\b(?:usd|eur|gbp|cad|aud|jpy|cny|chf|ars|mxn|d[oó]lar\w*|euro\w*|"
    r"libra\w*|iene\w*|peso\w*|bitcoin|btc)\b|US\$|€|£|¥|(?<!R)\$"
)
_NUMBER = r"(?<![\d.,-])\d+(?:\.\d{3})*(?:,\d{1,2})?(?![\d.,])"
_AMOUNT = re.compile(
    rf"(?i)(?:R\$|BRL)\s*({_NUMBER})|({_NUMBER})\s*(?:reais\b|real\b|BRL\b)"
)
_CONFIRMATION = re.compile(
    r"(?i)^\s*(?:sim(?:,?\s+pode\s+registrar)?|confirmo|confirmado|"
    r"pode\s+(?:registrar|lançar)|registre|ok)\s*[.!]?\s*$"
)


def explicit_brl(text: str, amount: float) -> bool:
    if not math.isfinite(amount) or amount <= 0 or FOREIGN.search(text):
        return False
    try:
        amounts = [
            Decimal(
                (match.group(1) or match.group(2)).replace(".", "").replace(",", ".")
            )
            for match in _AMOUNT.finditer(text)
        ]
        return len(amounts) == 1 and amounts[0] == Decimal(str(amount))
    except InvalidOperation:
        return False


def brl_statement(statements: tuple[str, ...], amount: float) -> str | None:
    """Resolve explicit currency only across narrow confirmation continuations.

    Stop at the nearest substantive human message; never fish older purchases
    out of the session when a new request, currency or value intervened. Intent
    and merchant correspondence are still checked by the evidence validator.
    """
    if not statements or not math.isfinite(amount) or amount <= 0:
        return None
    for text in reversed(statements[-6:]):
        if explicit_brl(text, amount):
            return text
        if _CONFIRMATION.fullmatch(text):
            continue
        stripped = text.strip()
        if re.fullmatch(_NUMBER, stripped):
            value = Decimal(stripped.replace(".", "").replace(",", "."))
            if value == Decimal(str(amount)):
                continue
        return None
    return None
