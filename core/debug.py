from starlette.middleware.base import BaseHTTPMiddleware
from app.config import DEBUG
from core.database import Database, Base
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, TIMESTAMP, func, inspect
import psutil
import time
from core.logger import Logger
import os

ASSET_EXTENSIONS = frozenset({
    ".css", ".js", ".jpg", ".jpeg", ".webp", ".png",
    ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".json",
})


class DebugModel(Base):
    __tablename__ = "debug"
    id = Column(Integer, primary_key=True)
    path = Column(String)
    method = Column(String)
    ip = Column(String)
    ram_used = Column(String)
    ram_total = Column(String)
    ram_percent = Column(String)
    ram = Column(String)
    cpu = Column(String)
    time_execution = Column(String)
    status_code = Column(String)
    user_agent = Column(String)
    created_at = Column(TIMESTAMP, default=func.now())


db = Database(config={"type": "sqlite", "database": "debug"})
db.connect()


class DebugMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.db = db
        self.createTables()

    def _get_session(self):
        return self.db.get_session()

    async def dispatch(self, request, call_next):
        if not DEBUG:
            return await call_next(request)

        path_ = request.url.path
        if path_ in ("/debug", "/debug/"):
            return await call_next(request)

        if any(path_.endswith(ext) for ext in ASSET_EXTENSIONS):
            return await call_next(request)

        try:
            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss
            cpu_times_before = process.cpu_times()
            cpu_before = cpu_times_before.user + cpu_times_before.system
            start_time = time.time()

            response = await call_next(request)

            end_time = time.time()
            time_execution = f"{end_time - start_time:.6f}s"
            ram = psutil.virtual_memory()
            mem_after = process.memory_info().rss
            mem_diff = mem_after - mem_before
            mem_diff_mb = round(mem_diff / (1024 * 1024), 4)
            ram_used = f"{mem_diff_mb}MB"
            ram_total = f"{round(ram.total / (1024 * 1024), 2)}MB"
            ram_percent = f"{round(ram.percent, 2)}%"
            cpu_times_after = process.cpu_times()
            cpu_after = cpu_times_after.user + cpu_times_after.system
            cpu_diff = cpu_after - cpu_before
            cpu_diff_ms = round(cpu_diff * 1000, 4)
            cpu = f"{cpu_diff_ms} ms"
            status_code = response.status_code
            user_agent = request.headers.get("user-agent", "Unknown")
            ip = request.client.host if request.client else "Unknown"

            session = self._get_session()
            try:
                session.add(DebugModel(
                    path=path_,
                    method=request.method,
                    ip=ip,
                    ram=ram_used,
                    ram_used=ram_used,
                    ram_total=ram_total,
                    ram_percent=ram_percent,
                    cpu=cpu,
                    time_execution=time_execution,
                    status_code=str(status_code),
                    user_agent=user_agent
                ))
                session.commit()
            finally:
                session.close()

            return response

        except Exception as e:
            Logger.error(f"Error in DebugMiddleware: {str(e)}")
            return await call_next(request)

    def createTables(self):
        if not DEBUG:
            return
        inspector = inspect(self.db.engine)
        if not inspector.has_table("debug"):
            self.db.migrate(use_base=True)