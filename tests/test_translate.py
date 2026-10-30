import unittest

from jinja2 import Environment

from lila.core.translate import Translate


class TranslationTests(unittest.TestCase):
    def test_missing_key_uses_jinja_default(self):
        env = Environment()
        template = env.from_string("{{ translate['missing-key'] | default('Fallback') }}")
        self.assertEqual(template.render(translate=Translate.get_dict("en")), "Fallback")

    def test_keys_are_case_insensitive(self):
        env = Environment()
        template = env.from_string("{{ translate['Name'] }}")
        self.assertEqual(template.render(translate=Translate.get_dict("en")), "Name")

    def test_chinese_locale_exists(self):
        self.assertEqual(Translate.get_dict("zh").get("login"), "欢迎回来")

    def test_accept_language_quality_order(self):
        class Req:
            query_params = {}
            cookies = {}
            headers = {"accept-language": "fr;q=0.1, es;q=0.9, en;q=0.5"}

        self.assertEqual(Translate.lang(Req()), "es")


if __name__ == "__main__":
    unittest.main()
