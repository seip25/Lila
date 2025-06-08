import os
import datetime
from datetime import timedelta
import traceback
from core.request import Request
import re

if not os.path.exists("system/logs/"):
    os.makedirs("system/logs/")


def folder_logs(type):
    now = datetime.datetime.now().strftime("%d-%m-%Y")
    path_ = f"system/logs/{now}"
    os.makedirs(path_, exist_ok=True)
    return f"{path_}/{type}.log"


class Logger:

    @classmethod
    def _write_log(cls, log_type, message):
        log_file = folder_logs(log_type)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as file:
            file.write(f"{timestamp} - {log_type.upper()} - {message}\n\n\n")

    @classmethod
    def error(cls, message: str, exception: Exception = None):
        if exception:
            message += f"\n{traceback.format_exc()}"
        cls._write_log("error", message)

    @classmethod
    def warning(cls, message: str):
        cls._write_log("warning", message)

    @classmethod
    def info(cls, message: str):
        cls._write_log("info", message)

    @classmethod
    def log(cls,log_type:str,message:str)->None:
        cls._write_log(log_type,message)

    @classmethod
    async def request(cls, request: Request):
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "Unknown")
        os_info = "Unknown"

        os_patterns = {
            "Windows": r"Windows NT|Windows",
            "Linux": r"Linux|X11",
            "Mac OS": r"Macintosh|Mac OS X",
            "iOS": r"iPhone|iPad|iPod",
            "Android": r"Android",
        }

        for os_name, pattern in os_patterns.items():
            if re.search(pattern, user_agent, re.IGNORECASE):
                os_info = os_name
                break
        try:
            body = await request.body()
            body_content = body.decode() if body else ""
            if "password" in body_content:
                body_content["password"] = ""
            if "password_2" in body_content:
                body_content["password_2"] = ""
            if "token" in body_content:
                body_content["token"] = ""
        except Exception as e:
            body_content = ""
        try:
            json_content = await request.json()
            if "password" in json_content:
                json_content["password"] = ""
            if "password_2" in json_content:
                json_content["password_2"] = ""
            if "token" in json_content:
                json_content["token"] = ""

        except Exception as e:
            json_content = {}
        return (
            f"IP: {client_ip}, "
            f"OS: {os_info}, "
            f"URL: {request.url.path}, "
            f"Method: {request.method} | "
            f"Query Params: {dict(request.query_params)} | "
            f"Path Params: {request.path_params} | "
            f"Body: {body_content} | "
            f"JSON: {json_content}"
        )


def delete_old_logs(days: int = 30):
    now = datetime.datetime.now()
    for folder_name in os.listdir("system/logs"):
        folder_path = os.path.join("system/logs", folder_name)
        try:
            folder_date = datetime.datetime.strptime(folder_name, "%d-%m-%Y")
            if now - folder_date > timedelta(days=days):
                for file in os.listdir(folder_path):
                    os.remove(os.path.join(folder_path, file))
                os.rmdir(folder_path)
        except ValueError:
            continue


delete_old_logs()
