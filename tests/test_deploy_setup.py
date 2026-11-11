import os
import tempfile
import unittest
from unittest import mock

from lila.cli.deploy_setup import read_env_file, run_setup, update_env_file


ENV = """# comment kept
SECRET_KEY=""
DEBUG=True
HOST="0.0.0.0"
PORT=8000
APP_URL="http://127.0.0.1:8000"
TITLE_PROJECT='My Shop'
LANG_DEFAULT='es'
CACHE_DRIVER="memory"
"""


class EnvFileTests(unittest.TestCase):
    def test_update_preserves_comments_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as fh:
                fh.write(ENV)
            update_env_file(path, {"DEBUG": "False", "NEW_KEY": "x"})
            text = open(path).read()
            self.assertTrue(text.startswith("# comment kept\n"))
            self.assertIn('DEBUG="False"', text)
            self.assertNotIn("DEBUG=True", text)
            self.assertTrue(text.rstrip().endswith('NEW_KEY="x"'))
            self.assertTrue(os.path.isfile(path + ".bak"))
            self.assertEqual(read_env_file(path)["TITLE_PROJECT"], "My Shop")


class SetupWizardTests(unittest.TestCase):
    def _project(self, tmp):
        project = os.path.join(tmp, "shop")
        os.makedirs(os.path.join(project, "public"))
        with open(os.path.join(project, ".env"), "w") as fh:
            fh.write(ENV)
        etc = os.path.join(tmp, "etc")
        os.makedirs(os.path.join(etc, "nginx", "sites-available"))
        os.makedirs(os.path.join(etc, "nginx", "sites-enabled"))
        return project, etc

    def test_interactive_answers_and_planned_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, etc = self._project(tmp)
            os.chmod(tmp, 0o700)                       # nginx cannot traverse
            os.chmod(os.path.join(project, ".env"), 0o644)
            answers = iter([
                "s",              # DEBUG -> False
                "S",              # HOST -> 127.0.0.1
                "shop.example.com",
                "",               # port: keep 8000
                "",               # service name: default slug
                "deploy",         # user
                "",               # workers: 1
                "s",              # nginx
                "s",              # https
                "ops@example.com",
                "s",              # chown project to 'deploy'
                "s",              # chmod o+x parents + public
                "s",              # .env -> 600
                "s",              # proceed
            ])
            with mock.patch("lila.cli.deploy_setup.shutil.which", return_value="/usr/bin/x"):
                result = run_setup(
                    project,
                    dry_run=True,
                    etc_root=etc,
                    input_fn=lambda _: next(answers),
                    is_root=True,
                    skip_platform_check=True,
                )
            self.assertEqual(result["domain"], "shop.example.com")
            self.assertEqual(result["service"], "my-shop")
            self.assertEqual(result["port"], 8000)
            updates = result["env_updates"]
            self.assertEqual(updates["DEBUG"], "False")
            self.assertEqual(updates["HOST"], "127.0.0.1")
            self.assertEqual(updates["APP_URL"], "https://shop.example.com")
            self.assertNotIn("SECRET_KEY", updates)   # never rotated by the wizard
            cmds = "\n".join(result["commands"])
            self.assertIn("systemctl enable --now my-shop.service", cmds)
            self.assertIn("nginx -t", cmds)
            self.assertIn("certbot --nginx", cmds)
            self.assertIn("-m ops@example.com -d shop.example.com", cmds)
            self.assertIn(f"chown -R deploy:deploy {project}", cmds)
            self.assertIn(f"chmod o+x {tmp}", cmds)
            self.assertIn("chmod -R o+rX", cmds)
            self.assertIn("chmod 600", cmds)
            # dry-run never touches .env
            self.assertIn("DEBUG=True", open(os.path.join(project, ".env")).read())
            self.assertTrue(os.path.isfile(os.path.join(project, "deploy", "my-shop.service")))

    def test_yes_mode_requires_real_domain(self):
        import typer

        with tempfile.TemporaryDirectory() as tmp:
            project, etc = self._project(tmp)
            with self.assertRaises(typer.Exit):
                run_setup(project, assume_yes=True, etc_root=etc, is_root=True, skip_platform_check=True)

    def test_real_run_installs_files_and_rolls_back_bad_nginx(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, etc = self._project(tmp)
            update_env_file(os.path.join(project, ".env"), {"APP_URL": "https://shop.example.com"}, backup=False)

            def fake_run(cmd):
                code = 1 if cmd[:2] == ["nginx", "-t"] else 0
                return mock.Mock(returncode=code)

            with mock.patch("lila.cli.deploy_setup.shutil.which", return_value="/usr/bin/x"), \
                    mock.patch("lila.cli.deploy_setup.subprocess.run", side_effect=fake_run), \
                    mock.patch("lila.cli.deploy_setup._healthcheck", return_value=200):
                result = run_setup(project, assume_yes=True, etc_root=etc, is_root=True, skip_platform_check=True)
            self.assertFalse(result["dry_run"])
            self.assertTrue(os.path.isfile(os.path.join(etc, "systemd", "system", "my-shop.service")))
            self.assertTrue(os.path.isfile(os.path.join(etc, "nginx", "sites-available", "shop.example.com.conf")))
            # nginx -t failed: the enabled symlink is removed and certbot is skipped
            self.assertFalse(os.path.lexists(os.path.join(etc, "nginx", "sites-enabled", "shop.example.com.conf")))
            self.assertFalse(any(c.startswith("certbot") for c in result["commands"]))
            env = read_env_file(os.path.join(project, ".env"))
            self.assertEqual(env["DEBUG"], "False")
            self.assertEqual(env["HOST"], "127.0.0.1")

    def test_yes_mode_and_not_root_forces_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, etc = self._project(tmp)
            update_env_file(os.path.join(project, ".env"), {"APP_URL": "https://example.com"}, backup=False)
            with mock.patch("lila.cli.deploy_setup.shutil.which", return_value="/usr/bin/x"):
                result = run_setup(project, assume_yes=True, etc_root=etc, is_root=False, skip_platform_check=True)
            self.assertTrue(result["dry_run"])
            self.assertFalse(os.path.lexists(os.path.join(etc, "nginx", "sites-enabled", "example.com.conf")))


if __name__ == "__main__":
    unittest.main()
