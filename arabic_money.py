"""Arabic monetary wording with decimal-safe rounding; no network required."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


@dataclass(frozen=True)
class Unit:
    singular: str
    dual: str
    plural: str
    accusative: str
    feminine: bool = False


def unit(one, two, many, accusative=None, feminine=False):
    return Unit(one, two, many, accusative or one, feminine)


RIYAL = unit("ريال سعودي", "ريالان سعوديان", "ريالات سعودية", "ريالًا سعوديًا")
HALALA = unit("هللة", "هللتان", "هللات", "هللة", True)
FILS = unit("فلس", "فلسان", "فلوس", "فلسًا")
QIRSH = unit("قرش", "قرشان", "قروش", "قرشًا")
CENT = unit("سنت", "سنتان", "سنتات", "سنتًا")
MILLIME = unit("مليم", "مليمان", "مليمات", "مليمًا")


def dinar(country, dual_country, plural_country):
    return unit("دينار " + country, "ديناران " + dual_country,
                "دنانير " + plural_country, "دينارًا " + country + "ًا")


def pound(country, dual_country, plural_country):
    return unit("جنيه " + country, "جنيهان " + dual_country,
                "جنيهات " + plural_country, "جنيهًا " + country + "ًا")


def lira(country, dual_country, plural_country):
    return unit("ليرة " + country, "ليرتان " + dual_country,
                "ليرات " + plural_country, feminine=True)


# Decimal places follow the currency's minor-unit exponent.
CURRENCY_UNITS = {
    "SAR": (RIYAL, HALALA, 2),
    "USD": (unit("دولار أمريكي", "دولاران أمريكيان", "دولارات أمريكية", "دولارًا أمريكيًا"), CENT, 2),
    "EUR": (unit("يورو", "يوروان", "يوروهات"), CENT, 2),
    "GBP": (pound("إسترليني", "إسترلينيان", "إسترلينية"), unit("بنس", "بنسان", "بنسات", "بنسًا"), 2),
    "KWD": (dinar("كويتي", "كويتيان", "كويتية"), FILS, 3),
    "BHD": (dinar("بحريني", "بحرينيان", "بحرينية"), FILS, 3),
    "OMR": (unit("ريال عماني", "ريالان عمانيان", "ريالات عمانية", "ريالًا عمانيًا"), unit("بيسة", "بيستان", "بيسات", feminine=True), 3),
    "QAR": (unit("ريال قطري", "ريالان قطريان", "ريالات قطرية", "ريالًا قطريًا"), unit("درهم", "درهمان", "دراهم", "درهمًا"), 2),
    "AED": (unit("درهم إماراتي", "درهمان إماراتيان", "دراهم إماراتية", "درهمًا إماراتيًا"), FILS, 2),
    "EGP": (pound("مصري", "مصريان", "مصرية"), QIRSH, 2),
    "JOD": (dinar("أردني", "أردنيان", "أردنية"), FILS, 3),
    "IQD": (dinar("عراقي", "عراقيان", "عراقية"), FILS, 3),
    "SYP": (lira("سورية", "سوريتان", "سورية"), QIRSH, 2),
    "LBP": (lira("لبنانية", "لبنانيتان", "لبنانية"), QIRSH, 2),
    "YER": (unit("ريال يمني", "ريالان يمنيان", "ريالات يمنية", "ريالًا يمنيًا"), FILS, 2),
    "SDG": (pound("سوداني", "سودانيان", "سودانية"), QIRSH, 2),
    "MAD": (unit("درهم مغربي", "درهمان مغربيان", "دراهم مغربية", "درهمًا مغربيًا"), unit("سنتيم", "سنتيمان", "سنتيمات", "سنتيمًا"), 2),
    "DZD": (dinar("جزائري", "جزائريان", "جزائرية"), unit("سنتيم", "سنتيمان", "سنتيمات", "سنتيمًا"), 2),
    "TND": (dinar("تونسي", "تونسيان", "تونسية"), MILLIME, 3),
    "LYD": (dinar("ليبي", "ليبيان", "ليبية"), unit("درهم", "درهمان", "دراهم", "درهمًا"), 3),
    "TRY": (lira("تركية", "تركيتان", "تركية"), QIRSH, 2),
    "JPY": (unit("ين ياباني", "ينان يابانيان", "ينات يابانية", "ينًا يابانيًا"), None, 0),
    "CNY": (unit("يوان صيني", "يوانان صينيان", "يوانات صينية", "يوانًا صينيًا"), unit("فن", "فنان", "فنات", "فنًا"), 2),
    "CHF": (unit("فرنك سويسري", "فرنكان سويسريان", "فرنكات سويسرية", "فرنكًا سويسريًا"), unit("سنتيم", "سنتيمان", "سنتيمات", "سنتيمًا"), 2),
}

ONES_M = ("", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة")
ONES_F = ("", "واحدة", "اثنتان", "ثلاث", "أربع", "خمس", "ست", "سبع", "ثمان", "تسع")
TENS = ("", "", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون")
HUNDREDS = ("", "مائة", "مائتان", "ثلاثمائة", "أربعمائة", "خمسمائة", "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة")
SCALES = (
    (10**12, unit("تريليون", "تريليونان", "تريليونات", "تريليونًا")),
    (10**9, unit("مليار", "ملياران", "مليارات", "مليارًا")),
    (10**6, unit("مليون", "مليونان", "ملايين", "مليونًا")),
    (10**3, unit("ألف", "ألفان", "آلاف", "ألفًا")),
)
MAX_AMOUNT = Decimal("1000000000000000")


def _under_hundred(n, feminine=False):
    ones = ONES_F if feminine else ONES_M
    if n < 10:
        return ones[n]
    if n == 10:
        return "عشر" if feminine else "عشرة"
    if n == 11:
        return "إحدى عشرة" if feminine else "أحد عشر"
    if n == 12:
        return "اثنتا عشرة" if feminine else "اثنا عشر"
    if n < 20:
        return ones[n - 10] + (" عشرة" if feminine else " عشر")
    tens, remainder = divmod(n, 10)
    return (ones[remainder] + " و" if remainder else "") + TENS[tens]


def _count(n, noun):
    if n == 0:
        return "صفر " + noun.singular
    if n == 1:
        return noun.singular + (" واحدة" if noun.feminine else " واحد")
    if n == 2:
        return noun.dual
    for scale, scale_unit in SCALES:
        if n >= scale:
            groups, rest = divmod(n, scale)
            prefix = scale_unit.singular if groups == 1 else _count(groups, scale_unit)
            if rest:
                return prefix + " و" + _count(rest, noun)
            if groups == 2:
                prefix = scale_unit.dual[:-1]  # ألفا ريال، مليونا ريال
            prefix = prefix.replace("ًا", "")
            return prefix + " " + noun.singular
    if n >= 100:
        hundreds, rest = divmod(n, 100)
        if rest:
            return HUNDREDS[hundreds] + " و" + _count(rest, noun)
        prefix = "مائتا" if hundreds == 2 else HUNDREDS[hundreds]
        return prefix + " " + noun.singular
    name = noun.plural if n <= 10 else noun.accusative
    return _under_hundred(n, noun.feminine) + " " + name


def parse_amount(value):
    text = str(value).strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    text = text.replace("٬", "").replace("٫", ".").replace(" ", "").replace("\u00a0", "")
    if "," in text:
        if "." in text:
            if not re.fullmatch(r"[+]?[0-9]{1,3}(,[0-9]{3})+[.][0-9]+", text):
                raise ValueError("صيغة المبلغ غير صحيحة")
            text = text.replace(",", "")
        elif text.count(",") == 1:
            text = text.replace(",", ".")
        else:
            raise ValueError("استخدم الفاصلة العشرية مرة واحدة")
    if len(text) > 40 or not re.fullmatch(r"[+]?(?:[0-9]+(?:[.][0-9]*)?|[.][0-9]+)", text):
        raise ValueError("الرجاء إدخال مبلغ موجب أو صفر")
    amount = Decimal(text)
    if not amount.is_finite() or amount < 0 or amount >= MAX_AMOUNT:
        raise ValueError("المبلغ خارج النطاق المدعوم")
    return amount


def rounded_amount(value, currency):
    amount = Decimal(str(value))
    if not amount.is_finite() or abs(amount) >= MAX_AMOUNT:
        raise ValueError("المبلغ خارج النطاق المدعوم")
    precision = CURRENCY_UNITS[currency][2]
    with localcontext() as ctx:
        ctx.prec = 40
        result = amount.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    if abs(result) >= MAX_AMOUNT:
        raise ValueError("المبلغ خارج النطاق المدعوم")
    return result


def amount_in_words(value, currency):
    amount = rounded_amount(value, currency)
    major, minor, precision = CURRENCY_UNITS[currency]
    absolute = abs(amount)
    whole = int(absolute)
    fraction = int((absolute - whole) * 10**precision)
    words = _count(whole, major)
    if fraction and minor is not None:
        words += " و" + _count(fraction, minor)
    return ("سالب " if amount < 0 else "") + words


def format_amount(value, currency):
    precision = CURRENCY_UNITS[currency][2]
    return format(rounded_amount(value, currency), f",.{precision}f").translate(
        str.maketrans("0123456789,.", "٠١٢٣٤٥٦٧٨٩٬٫")
    )
