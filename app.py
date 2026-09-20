"""
محول العملات - تطبيق أندرويد بواجهة عربية
Currency Converter - Arabic-interface Android app built with Toga/Briefcase.

يعرض التطبيق تحويل فوري بين العملات، ويقوم بتحديث الأسعار تلقائياً كل فترة
زمنية محددة، ويُظهر سهم ارتفاع (أخضر ▲) أو انخفاض (أحمر ▼) بجانب كل عملة
مقارنة بآخر قراءة.

مصدر الأسعار: open.er-api.com (مجاني، لا يحتاج مفتاح API).
ملاحظة: مزوّدو الأسعار المجانيون يحدّثون بياناتهم عادة مرة كل 24 ساعة،
لذلك "التحديث اللحظي" هنا يعني: يتحقق التطبيق من المصدر بشكل دوري، وبمجرد
صدور سعر جديد من المزوّد يظهر فوراً مع سهم يوضح اتجاه التغيّر.
"""

import asyncio
import json
from decimal import Decimal, InvalidOperation

try:
    from .arabic_money import parse_amount, rounded_amount, amount_in_words, format_amount
except ImportError:
    from arabic_money import parse_amount, rounded_amount, amount_in_words, format_amount
from datetime import datetime
from pathlib import Path

import httpx
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, CENTER, RIGHT, LEFT

# ---------------------------------------------------------------------------
# بيانات العملات: الرمز -> (الاسم بالعربية, رمز/علم اختياري)
# ---------------------------------------------------------------------------
CURRENCIES = {
    "USD": "دولار أمريكي",
    "EUR": "يورو",
    "GBP": "جنيه إسترليني",
    "SAR": "ريال سعودي",
    "KWD": "دينار كويتي",
    "BHD": "دينار بحريني",
    "OMR": "ريال عماني",
    "QAR": "ريال قطري",
    "AED": "درهم إماراتي",
    "EGP": "جنيه مصري",
    "JOD": "دينار أردني",
    "IQD": "دينار عراقي",
    "SYP": "ليرة سورية",
    "LBP": "ليرة لبنانية",
    "YER": "ريال يمني",
    "SDG": "جنيه سوداني",
    "MAD": "درهم مغربي",
    "DZD": "دينار جزائري",
    "TND": "دينار تونسي",
    "LYD": "دينار ليبي",
    "TRY": "ليرة تركية",
    "JPY": "ين ياباني",
    "CNY": "يوان صيني",
    "CHF": "فرنك سويسري",
}

# ترتيب العرض الافتراضي (يبدأ بالعملات التي طلبها المستخدم)
DEFAULT_ORDER = [
    "SYP", "BHD", "SAR", "KWD", "EGP", "TRY", "JOD", "IQD", "OMR",
    "AED", "QAR", "LBP", "MAD", "DZD", "TND", "LYD", "YER", "SDG",
    "USD", "EUR", "GBP", "JPY", "CNY", "CHF",
]

API_URL = "https://open.er-api.com/v6/latest/USD"
POLL_SECONDS = 60  # كم ثانية بين كل تحقق من الأسعار


def currency_label(code: str) -> str:
    """يبني تسمية عربية للعملة مثل: ريال سعودي (SAR)"""
    return f"{CURRENCIES.get(code, code)} ({code})"


class CurrencyConverterApp(toga.App):

    def startup(self):
        # rates: code -> rate relative to USD (1 USD = rate * code)
        self.rates: dict[str, float] = {}
        self.previous_rates: dict[str, float] = {}
        self.last_updated: datetime | None = None
        self.cache_file = Path(self.paths.data) / "rates_cache.json"

        self._load_cache()

        self.main_window = toga.MainWindow(title="محول العملات")

        converter_box = self._build_converter_view()
        rates_box = self._build_rates_view()

        container = toga.OptionContainer(
            content=[
                ("التحويل", converter_box),
                ("الأسعار المباشرة", rates_box),
            ],
            style=Pack(flex=1),
        )

        self.main_window.content = container
        self.main_window.show()

        # يبدأ التحديث الدوري في الخلفية فور فتح التطبيق
        self.add_background_task(self.poll_rates_loop)

    # ------------------------------------------------------------------
    # واجهة التحويل
    # ------------------------------------------------------------------
    def _build_converter_view(self) -> toga.Box:
        labels = [currency_label(c) for c in DEFAULT_ORDER]

        title = toga.Label(
            "محول العملات",
            style=Pack(text_align=CENTER, font_size=20, font_weight="bold",
                       padding=(10, 5)),
        )

        amount_row = toga.Box(style=Pack(direction=ROW, padding=5, alignment=CENTER))
        amount_label = toga.Label("المبلغ:", style=Pack(text_align=RIGHT, padding_right=8, width=70))
        self.amount_input = toga.TextInput(
            value="1", style=Pack(flex=1, text_align=RIGHT)
        )
        amount_row.add(self.amount_input)
        amount_row.add(amount_label)

        from_row = toga.Box(style=Pack(direction=ROW, padding=5, alignment=CENTER))
        from_label = toga.Label("من عملة:", style=Pack(text_align=RIGHT, padding_right=8, width=70))
        self.from_selection = toga.Selection(items=labels, style=Pack(flex=1))
        self.from_selection.value = currency_label("USD")
        from_row.add(self.from_selection)
        from_row.add(from_label)

        to_row = toga.Box(style=Pack(direction=ROW, padding=5, alignment=CENTER))
        to_label = toga.Label("إلى عملة:", style=Pack(text_align=RIGHT, padding_right=8, width=70))
        self.to_selection = toga.Selection(items=labels, style=Pack(flex=1))
        self.to_selection.value = currency_label("SAR")
        to_row.add(self.to_selection)
        to_row.add(to_label)

        swap_button = toga.Button(
            "⇅ عكس العملتين",
            on_press=self._swap_currencies,
            style=Pack(padding=5),
        )

        convert_button = toga.Button(
            "تحويل",
            on_press=self._on_convert,
            style=Pack(padding=10, background_color="#1565C0", color="#FFFFFF"),
        )

        self.result_label = toga.Label(
            "",
            style=Pack(text_align=CENTER, font_size=22, font_weight="bold",
                       padding=15, color="#1565C0"),
        )

        self.words_output = toga.MultilineTextInput(
            readonly=True,
            placeholder="النتيجة بالحروف العربية",
            style=Pack(height=100, padding=5, font_size=16, text_align=RIGHT),
        )

        self.status_label = toga.Label(
            "جاري تحميل الأسعار...",
            style=Pack(text_align=CENTER, font_size=11, color="#666666", padding=5),
        )

        refresh_button = toga.Button(
            "⟳ تحديث الآن",
            on_press=self._manual_refresh,
            style=Pack(padding=5),
        )

        box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        for widget in (
            title, amount_row, from_row, to_row, swap_button,
            convert_button, self.result_label, self.words_output, self.status_label, refresh_button,
        ):
            box.add(widget)

        scroller = toga.ScrollContainer(content=box, style=Pack(flex=1))
        return scroller

    def _swap_currencies(self, widget):
        self.from_selection.value, self.to_selection.value = (
            self.to_selection.value, self.from_selection.value,
        )

    def _on_convert(self, widget):
        self._do_convert()

    def _do_convert(self):
        # Clear the previous wording so invalid input never leaves a stale amount.
        self.words_output.value = ""
        if not self.rates:
            self.result_label.text = "الأسعار غير متوفرة بعد"
            return
        try:
            amount = parse_amount(self.amount_input.value)
            from_code = self._code_from_label(self.from_selection.value)
            to_code = self._code_from_label(self.to_selection.value)
            from_rate = Decimal(str(self.rates.get(from_code, 0)))
            to_rate = Decimal(str(self.rates.get(to_code, 0)))
            if not from_rate.is_finite() or not to_rate.is_finite() or from_rate <= 0 or to_rate <= 0:
                self.result_label.text = "تعذر إيجاد سعر لهذه العملة"
                return
            converted = rounded_amount(amount / from_rate * to_rate, to_code)
            self.result_label.text = f"{format_amount(converted, to_code)} {CURRENCIES[to_code]}"
            self.words_output.value = amount_in_words(converted, to_code)
        except (ValueError, InvalidOperation, KeyError):
            self.result_label.text = "الرجاء إدخال مبلغ صحيح ضمن النطاق المدعوم"

    @staticmethod
    def _code_from_label(label: str) -> str:
        # التسمية بالشكل: "ريال سعودي (SAR)"
        return label.split("(")[-1].rstrip(")")

    # ------------------------------------------------------------------
    # واجهة الأسعار المباشرة (قائمة كل العملات مع سهم الاتجاه)
    # ------------------------------------------------------------------
    def _build_rates_view(self) -> toga.Box:
        title = toga.Label(
            "الأسعار مقابل الدولار الأمريكي",
            style=Pack(text_align=CENTER, font_size=16, font_weight="bold", padding=10),
        )
        self.rates_last_updated_label = toga.Label(
            "", style=Pack(text_align=CENTER, font_size=11, color="#666666", padding_bottom=5),
        )

        self.rates_rows_box = toga.Box(style=Pack(direction=COLUMN, padding=5))
        self._rate_row_widgets: dict[str, toga.Label] = {}

        for code in DEFAULT_ORDER:
            row = toga.Box(style=Pack(direction=ROW, padding=4, alignment=CENTER))
            name_label = toga.Label(
                currency_label(code),
                style=Pack(text_align=RIGHT, flex=1),
            )
            value_label = toga.Label(
                "...", style=Pack(text_align=LEFT, width=140, font_weight="bold"),
            )
            self._rate_row_widgets[code] = value_label
            row.add(value_label)
            row.add(name_label)
            self.rates_rows_box.add(row)

        box = toga.Box(style=Pack(direction=COLUMN, padding=10))
        box.add(title)
        box.add(self.rates_last_updated_label)
        box.add(self.rates_rows_box)

        return toga.ScrollContainer(content=box, style=Pack(flex=1))

    def _refresh_rates_view(self):
        for code, value_label in self._rate_row_widgets.items():
            rate = self.rates.get(code)
            if rate is None:
                value_label.text = "—"
                value_label.style.color = "#999999"
                continue

            prev = self.previous_rates.get(code)
            arrow, color = "", "#333333"
            if prev is not None and prev != 0:
                if rate > prev:
                    arrow, color = " ▲", "#2E7D32"   # أخضر: ارتفاع
                elif rate < prev:
                    arrow, color = " ▼", "#C62828"   # أحمر: انخفاض

            value_label.text = f"{rate:,.4f}{arrow}"
            value_label.style.color = color

        if self.last_updated:
            stamp = self.last_updated.strftime("%H:%M:%S")
            self.rates_last_updated_label.text = f"آخر تحديث: {stamp}"
            self.status_label.text = f"آخر تحديث: {stamp} (تحديث كل {POLL_SECONDS} ثانية)"

    # ------------------------------------------------------------------
    # جلب الأسعار (دوري + يدوي)
    # ------------------------------------------------------------------
    async def poll_rates_loop(self, widget=None, **kwargs):
        while True:
            await self._fetch_rates_once()
            await asyncio.sleep(POLL_SECONDS)

    def _manual_refresh(self, widget):
        self.add_background_task(self._fetch_rates_once)

    async def _fetch_rates_once(self, widget=None, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(API_URL)
                response.raise_for_status()
                data = response.json()

            new_rates = data.get("rates", {})
            if not new_rates:
                raise ValueError("لم يتم استلام أسعار من المصدر")

            if self.rates:
                self.previous_rates = dict(self.rates)
            self.rates = {code: new_rates[code] for code in CURRENCIES if code in new_rates}
            self.last_updated = datetime.now()

            self._save_cache()
            self._refresh_rates_view()
            self._do_convert()

        except Exception as exc:  # شبكة غير متاحة أو خطأ في الاستجابة
            self.status_label.text = f"تعذر تحديث الأسعار ({exc.__class__.__name__}) — سيُعاد المحاولة"

    # ------------------------------------------------------------------
    # تخزين مؤقت محلي حتى يعمل آخر سعر معروف بدون إنترنت
    # ------------------------------------------------------------------
    def _load_cache(self):
        try:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                self.rates = data.get("rates", {})
                stamp = data.get("last_updated")
                if stamp:
                    self.last_updated = datetime.fromisoformat(stamp)
        except Exception:
            pass  # تجاهل أي عطل في التخزين المؤقت والبدء بحالة فارغة

    def _save_cache(self):
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(
                json.dumps(
                    {
                        "rates": self.rates,
                        "last_updated": self.last_updated.isoformat() if self.last_updated else None,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass


def main():
    return CurrencyConverterApp("محول العملات", "com.almosheqh.currencyconverter")


if __name__ == "__main__":
    main().main_loop()
