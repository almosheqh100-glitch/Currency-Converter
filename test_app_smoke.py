"""Exercise the real Toga view and conversion handler without a network request."""
import asyncio
import os
os.environ["TOGA_BACKEND"] = "toga_dummy"
from app import main, currency_label, CurrencyConverterApp


async def exercise():
    async def idle(self, widget=None, **kwargs):
        await asyncio.Event().wait()
    CurrencyConverterApp.poll_rates_loop = idle
    application = main()
    application.rates = {"USD": 1, "SAR": 3.75, "KWD": 0.307}
    application.from_selection.value = currency_label("SAR")
    application.to_selection.value = currency_label("SAR")
    application.amount_input.value = "٣,٦٦"
    application._do_convert()
    assert application.words_output.value == "ثلاثة ريالات سعودية وست وستون هللة"
    assert application.result_label.text == "٣٫٦٦ ريال سعودي"
    application.to_selection.value = currency_label("KWD")
    application._do_convert()
    assert "دينار" in application.words_output.value
    application.amount_input.value = "NaN"
    application._do_convert()
    assert application.words_output.value == ""
    assert "الرجاء" in application.result_label.text
    print("Toga startup and Arabic conversion UI smoke test passed")


asyncio.run(exercise())
