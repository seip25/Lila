import os
import json
import unittest

from lila.core.translate import Translate


class LocalesParityTests(unittest.TestCase):
    def setUp(self):
        self.locales_dir = os.path.join(
            os.path.dirname(__file__), "..", "lila", "app", "locales"
        )
        self.languages = ["en", "es", "pt", "zh"]
        self.loaded_data = {}
        for lang in self.languages:
            file_path = os.path.join(self.locales_dir, f"{lang}.json")
            self.assertTrue(os.path.isfile(file_path), f"Locale file {file_path} missing")
            with open(file_path, "r", encoding="utf-8") as f:
                self.loaded_data[lang] = json.load(f)

    def test_all_locales_have_identical_keys(self):
        en_keys = set(self.loaded_data["en"].keys())
        self.assertGreater(len(en_keys), 50, "Should have dozens of translation keys")

        for lang in ("es", "pt", "zh"):
            lang_keys = set(self.loaded_data[lang].keys())
            missing_in_lang = en_keys - lang_keys
            extra_in_lang = lang_keys - en_keys
            self.assertEqual(
                missing_in_lang,
                set(),
                f"Locale '{lang}' is missing keys present in 'en': {missing_in_lang}",
            )
            self.assertEqual(
                extra_in_lang,
                set(),
                f"Locale '{lang}' has extra keys not present in 'en': {extra_in_lang}",
            )

    def test_no_empty_translations(self):
        for lang, data in self.loaded_data.items():
            for key, val in data.items():
                self.assertIsInstance(val, str, f"Key '{key}' in '{lang}' must be a string")
                self.assertTrue(
                    val.strip(),
                    f"Key '{key}' in '{lang}' is empty or whitespace only",
                )

    def test_builtin_locales_parity(self):
        builtin_en = set(Translate.BUILTIN_LOCALES["en"].keys())
        for lang in ("es", "pt", "zh"):
            builtin_lang = set(Translate.BUILTIN_LOCALES[lang].keys())
            missing = builtin_en - builtin_lang
            self.assertEqual(missing, set(), f"BUILTIN_LOCALES['{lang}'] missing keys: {missing}")

    def test_translation_helpers(self):
        self.assertEqual(Translate.t("login", lang="es"), "Bienvenido de nuevo")
        self.assertEqual(Translate.t("login", lang="en"), "Welcome Back")
        self.assertEqual(Translate.t("login", lang="pt"), "Bem-vindo de volta")
        self.assertEqual(Translate.t("login", lang="zh"), "欢迎回来")

        self.assertEqual(Translate.t("sign_in", lang="es"), "Iniciar Sesión")
        self.assertEqual(Translate.t("sign_in", lang="en"), "Sign In")
        self.assertEqual(Translate.t("sign_in", lang="pt"), "Entrar")
        self.assertEqual(Translate.t("sign_in", lang="zh"), "登录")

        self.assertEqual(Translate.t("register", lang="pt"), "Criar Conta")
        self.assertEqual(Translate.t("register", lang="zh"), "创建账户")


if __name__ == "__main__":
    unittest.main()
