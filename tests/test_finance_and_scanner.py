import unittest
from decimal import Decimal

from services.finance_calc import (
    parse_decimal, parse_percent, calculate_profit, calculate_reverse, calculate_tax
)
from services.text_scanner import scan_text


class FinanceTests(unittest.TestCase):
    def test_localized_money_input(self):
        self.assertEqual(parse_decimal("1 250,50 ₽"), Decimal("1250.50"))
        self.assertEqual(parse_decimal("1250.50 руб"), Decimal("1250.50"))

    def test_invalid_numbers_are_rejected(self):
        self.assertIsNone(parse_decimal("NaN"))
        self.assertIsNone(parse_decimal("-50"))
        self.assertIsNone(parse_decimal("9" * 50))
        self.assertIsNone(parse_percent("100"))

    def test_profit_and_roi(self):
        result = calculate_profit(Decimal("500"), Decimal("1000"), Decimal("5"))
        self.assertEqual(result.profit, Decimal("450"))
        self.assertEqual(result.margin_percent, Decimal("45"))
        self.assertEqual(result.roi_percent, Decimal("90"))

    def test_reverse_rounds_up_to_target(self):
        result = calculate_reverse(Decimal("1500"), Decimal("5"))
        self.assertEqual(result.listing_price, Decimal("1578.95"))
        self.assertGreaterEqual(result.net_amount, Decimal("1500"))

    def test_game_tax_receive(self):
        result = calculate_tax(Decimal("1000"), Decimal("10"), "receive")
        self.assertGreaterEqual(result.net_amount, Decimal("1000"))


class ScannerTests(unittest.TestCase):
    def test_high_risk_patterns(self):
        result = scan_text("Пиши в Telegram, оплата напрямую https://example.com")
        self.assertEqual(result.risk, "Высокий")
        self.assertGreaterEqual(len(result.issues), 3)

    def test_clean_description(self):
        result = scan_text("Цифровой товар. Выдача после оплаты, срок до 15 минут.")
        self.assertEqual(result.risk, "Безопасно по текущему словарю")
        self.assertEqual(len(result.issues), 0)


if __name__ == "__main__":
    unittest.main()
