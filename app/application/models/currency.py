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
