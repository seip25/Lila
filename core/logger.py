import os
import datetime
import logging
from datetime import timedelta
import traceback

if not os.path.exists('logs'):
    os.makedirs('logs')


def folder_logs(type):
    now = datetime.datetime.now().strftime("%d-%m-%Y")
    path_ = f"logs/{now}"
    os.makedirs(path_, exist_ok=True)
    return f"{path_}/{type}.log"


class Logger:
    
    @classmethod
    def _write_log(cls, log_type, message):
        log_file = folder_logs(log_type)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as file:
            file.write(f"{timestamp} - {log_type.upper()} - {message}\n")

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


def delete_old_logs(days: int = 30):
    now = datetime.datetime.now()
    for folder_name in os.listdir("logs"):
        folder_path = os.path.join("logs", folder_name)
        try:
            folder_date = datetime.datetime.strptime(folder_name, "%d-%m-%Y")
            if now - folder_date > timedelta(days=days):
                for file in os.listdir(folder_path):
                    os.remove(os.path.join(folder_path, file))
                os.rmdir(folder_path)
        except ValueError:
            continue


delete_old_logs()
