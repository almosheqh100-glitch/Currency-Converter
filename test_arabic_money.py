import unittest
from decimal import Decimal
from arabic_money import amount_in_words, format_amount, parse_amount, rounded_amount, CURRENCY_UNITS


class ArabicMoneyTests(unittest.TestCase):
    def test_requested_example(self):
        self.assertEqual(amount_in_words("3.66", "SAR"), "ثلاثة ريالات سعودية وست وستون هللة")
        self.assertEqual(format_amount("3.66", "SAR"), "٣٫٦٦")

    def test_arabic_and_decimal_comma_input(self):
        for text in ["3,66", "3 ,66", "٣٫٦٦", "٣,٦٦", "۳٫۶۶", "3.66"]:
            with self.subTest(text=text):
                self.assertEqual(parse_amount(text), Decimal("3.66"))
        self.assertEqual(parse_amount("١٬٢٣٤٫٥٦"), Decimal("1234.56"))
        self.assertEqual(parse_amount("1,234.56"), Decimal("1234.56"))

    def test_singular_dual_and_feminine(self):
        self.assertEqual(amount_in_words("1.01", "SAR"), "ريال سعودي واحد وهللة واحدة")
        self.assertEqual(amount_in_words("2.02", "SAR"), "ريالان سعوديان وهللتان")
        self.assertEqual(amount_in_words("3", "SYP"), "ثلاث ليرات سورية")
        self.assertEqual(amount_in_words("11", "SYP"), "إحدى عشرة ليرة سورية")
        self.assertEqual(amount_in_words("0", "SAR"), "صفر ريال سعودي")

    def test_rounding_and_minor_units(self):
        self.assertEqual(rounded_amount("3.665", "SAR"), Decimal("3.67"))
        self.assertEqual(amount_in_words("3.999", "SAR"), "أربعة ريالات سعودية")
        self.assertEqual(amount_in_words("3.006", "KWD"), "ثلاثة دنانير كويتية وستة فلوس")
        self.assertEqual(format_amount("3.006", "KWD"), "٣٫٠٠٦")
        self.assertEqual(amount_in_words("3.66", "JPY"), "أربعة ينات يابانية")

    def test_hundreds_and_thousands(self):
        self.assertEqual(amount_in_words("200", "SAR"), "مائتا ريال سعودي")
        self.assertEqual(amount_in_words("2000", "SAR"), "ألفا ريال سعودي")
        self.assertEqual(amount_in_words("1001", "SAR"), "ألف وريال سعودي واحد")
        self.assertEqual(amount_in_words("21", "SAR"), "واحد وعشرون ريالًا سعوديًا")

    def test_all_currencies(self):
        self.assertEqual(len(CURRENCY_UNITS), 24)
        for code in CURRENCY_UNITS:
            for value in ("0", "1", "2", "3.66", "11.12", "123456.789"):
                with self.subTest(code=code, value=value):
                    words = amount_in_words(value, code)
                    self.assertTrue(words)
                    self.assertFalse(any(char.isdigit() for char in words))
                    self.assertNotIn(code, words)

    def test_invalid_input(self):
        for text in ("", "NaN", "Infinity", "-1", "1e99", "3,,66", "1,2,3", "abc", "1000000000000000"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_amount(text)
        for text in ("NaN", "Infinity", "1000000000000000"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                amount_in_words(text, "SAR")


if __name__ == "__main__":
    unittest.main()
