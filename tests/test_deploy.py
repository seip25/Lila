import os
import stat
import tempfile
import unittest

from lila.cli.deploy import generate_deploy_files


class DeployTests(unittest.TestCase):
    def test_deploy_generates_all_required_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = os.path.join(tmp_dir, "deploy_out")
            info = generate_deploy_files(
                output_dir=out_dir,
                domain="myapp.example.com",
                port=4000,
                user="deployuser",
                group="deploygroup",
                workers=3,
                service_name="myapp",
                with_worker=True,
                project_dir=tmp_dir,
            )

            # Check files exist
            sh_path = info["sh_path"]
            service_path = info["service_path"]
            worker_path = info["worker_service_path"]
            nginx_path = info["nginx_path"]
            ps1_path = info["ps1_path"]

            self.assertTrue(os.path.isfile(sh_path), "start_lila.sh must exist")
            self.assertTrue(os.path.isfile(service_path), "systemd service file must exist")
            self.assertTrue(os.path.isfile(worker_path), "worker service file must exist")
            self.assertTrue(os.path.isfile(nginx_path), "nginx config must exist")
            self.assertTrue(os.path.isfile(ps1_path), "powershell script must exist")

            # Check contents of start_lila.sh
            with open(sh_path, "r", encoding="utf-8") as f:
                sh_content = f.read()
            self.assertIn("#!/usr/bin/env bash", sh_content)
            self.assertIn("lila run --host 127.0.0.1 --port 4000 -w 3 --proxy-headers", sh_content)

            # Check contents of myapp.service
            with open(service_path, "r", encoding="utf-8") as f:
                srv_content = f.read()
            self.assertIn("[Unit]", srv_content)
            self.assertIn("[Service]", srv_content)
            self.assertIn("User=deployuser", srv_content)
            self.assertIn("Group=deploygroup", srv_content)
            self.assertIn("Restart=always", srv_content)
            self.assertIn("LimitNOFILE=65535", srv_content)
            self.assertIn("start_lila.sh", srv_content)

            # Check contents of myapp-worker.service
            with open(worker_path, "r", encoding="utf-8") as f:
                worker_content = f.read()
            self.assertIn("Lila Framework Background Worker", worker_content)
            self.assertIn("lila worker", worker_content)
            self.assertIn("Restart=always", worker_content)

            # Check contents of myapp.example.com.nginx.conf
            with open(nginx_path, "r", encoding="utf-8") as f:
                nginx_content = f.read()
            self.assertIn("server_name myapp.example.com;", nginx_content)
            self.assertIn("proxy_pass http://127.0.0.1:4000;", nginx_content)
            self.assertIn("proxy_set_header Upgrade $http_upgrade;", nginx_content)
            self.assertIn("proxy_set_header Connection $connection_upgrade;", nginx_content)
            self.assertIn("client_max_body_size 50M;", nginx_content)
            self.assertIn("gzip_static on;", nginx_content)
            self.assertIn("proxy_set_header X-Forwarded-Proto $scheme;", nginx_content)

            # Check contents of start_lila.ps1
            with open(ps1_path, "r", encoding="utf-8") as f:
                ps1_content = f.read()
            self.assertIn("lila run --host 127.0.0.1 --port 4000 -w 3 --proxy-headers", ps1_content)


if __name__ == "__main__":
    unittest.main()
