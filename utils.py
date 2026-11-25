import html
from decimal import Decimal, ROUND_HALF_UP


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fmt_money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.2f}".replace(",", " ").replace(".", ",") + " ₽"


def fmt_number(value: Decimal, digits: int = 2) -> str:
    rounded = value.quantize(Decimal("1").scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{rounded:,.{digits}f}".replace(",", " ").replace(".", ",")


def short_date(value: str | None) -> str:
    if not value:
        return "не указано"
    return value.replace("T", " ")[:16] + " UTC"
