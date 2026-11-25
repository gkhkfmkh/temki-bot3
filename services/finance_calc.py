from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re


@dataclass(frozen=True, slots=True)
class ProfitResult:
    cost: Decimal
    sale: Decimal
    fee_percent: Decimal
    fee_amount: Decimal
    net_revenue: Decimal
    profit: Decimal
    margin_percent: Decimal
    roi_percent: Decimal | None
    status: str


@dataclass(frozen=True, slots=True)
class ReverseResult:
    target: Decimal
    fee_percent: Decimal
    listing_price: Decimal
    fee_amount: Decimal
    net_amount: Decimal


@dataclass(frozen=True, slots=True)
class TaxResult:
    mode: str
    amount: Decimal
    tax_percent: Decimal
    gross_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal


def parse_decimal(raw: str, *, allow_zero: bool = True) -> Decimal | None:
    """Accepts 1 250,50 ₽, 1250.50 and 1250 руб.; rejects NaN, inf and negatives."""
    text = str(raw or "").strip().lower()
    if len(text) > 40:
        return None
    text = text.replace("₽", "").replace("руб.", "").replace("руб", "")
    text = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    text = re.sub(r"(?<=\d)[_'](?=\d)", "", text)
    if not text or not re.fullmatch(r"\+?\d+(?:\.\d{1,6})?", text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    if (
        not value.is_finite()
        or value < 0
        or value > Decimal("999999999999999999")
        or (not allow_zero and value == 0)
    ):
        return None
    return value


def parse_percent(raw: str) -> Decimal | None:
    value = parse_decimal(str(raw).replace("%", ""), allow_zero=True)
    return value if value is not None and value < 100 else None


def calculate_profit(cost: Decimal, sale: Decimal, fee_percent: Decimal) -> ProfitResult:
    if cost < 0 or sale <= 0 or not 0 <= fee_percent < 100:
        raise ValueError("Проверьте закупку, цену продажи и комиссию.")
    fee = sale * fee_percent / Decimal(100)
    net = sale - fee
    profit = net - cost
    margin = profit / sale * Decimal(100)
    roi = profit / cost * Decimal(100) if cost > 0 else None
    status = "profit" if profit > 0 else "zero" if profit == 0 else "loss"
    return ProfitResult(cost, sale, fee_percent, fee, net, profit, margin, roi, status)


def calculate_reverse(target: Decimal, fee_percent: Decimal) -> ReverseResult:
    if target <= 0 or not 0 <= fee_percent < 100:
        raise ValueError("Сумма должна быть положительной, комиссия — от 0 до 99,99%.")
    raw_price = target / (Decimal(1) - fee_percent / Decimal(100))
    price = raw_price.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    fee = price * fee_percent / Decimal(100)
    return ReverseResult(target, fee_percent, price, fee, price - fee)


def calculate_tax(amount: Decimal, tax_percent: Decimal, mode: str) -> TaxResult:
    if amount <= 0 or not 0 <= tax_percent < 100:
        raise ValueError("Количество должно быть положительным, налог — от 0 до 99,99%.")
    rate = tax_percent / Decimal(100)
    if mode == "receive":
        gross = (amount / (Decimal(1) - rate)).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
        tax = gross * rate
        net = gross - tax
    elif mode == "send":
        gross = amount
        tax = gross * rate
        net = gross - tax
    else:
        raise ValueError("Неизвестный режим расчёта.")
    return TaxResult(mode, amount, tax_percent, gross, tax, net)
