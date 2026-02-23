from starlette.middleware.base import BaseHTTPMiddleware
from app.config import DEBUG
from core.database import Database,Base
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, TIMESTAMP, func,inspect
import psutil
import time
from core.logger import Logger 


class DebugModel(Base):
    __tablename__ = "debug"
    id = Column(Integer, primary_key=True)
    path = Column(String)
    method = Column(String)
    ip = Column(String)
    ram_used= Column(String)
    ram_total= Column(String)
    ram_percent= Column(String)
    ram= Column(String)
    cpu = Column(String)
    time_execution = Column(String)
    status_code = Column(String) 
    user_agent = Column(String) 
    created_at = Column(TIMESTAMP, default=func.now())


db = Database(config={"type":"sqlite","database":"debug"})
db.connect()
db_session_debug = db.get_session()



class DebugMiddleware(BaseHTTPMiddleware) :
    def __init__(self, app):
        super().__init__(app)
        self.db = db
        self.db_session = db_session_debug
        self.createTables()


    async def dispatch(self, request, call_next):
        if DEBUG:  
            path_=request.url.path
            if path_ != "/debug" and path_ != "/debug/" : 
                try:
                    start_time = time.time()
                    response = await call_next(request)
                    end_time = time.time() 
                    time_execution = f"{end_time - start_time:.6f}s"  
                    ram = psutil.virtual_memory() or "Unknown" 
                    ram_used = f"{str(round(ram.used/(1024*1024),2))}MB"
                    ram_total = f"{str(round(ram.total/(1024*1024),2))}MB"
                    ram_percent = f"{str(round(ram.percent,2))}%"
                    cpu = f"{psutil.cpu_percent() or "Unknown" }%"
                    status_code = response.status_code
                    if status_code >= 200 and status_code <= 299:
                        status_code = f"🟢 {status_code}"
                    elif status_code >= 400 and status_code <= 499:
                        status_code = f"🟡 {status_code}"
                    elif status_code >= 500 and status_code <= 599:
                        status_code = f"🔴 {status_code}"
                    user_agent = request.headers.get("user-agent") or "Unknown" 
                    ip = request.client.host or "Unknown" 
                    ram =f"""{ram_used}(Used)<br>{ram_total}(Total)<br>{ram_percent}(Percent)"""
                    type="route"
                    assets=[
                        "css",
                        "js",
                        "jpg",
                        "jpeg",
                        "webp",
                        "png",
                        "gif",
                        "ico",
                        "svg",
                        "woff",
                        "woff2",
                        "ttf",
                        "eot",
                        "json"
                    ]
                    if any(path_.endswith(ext) for ext in assets):
                        type="asset"
                    if type != "asset":
                        db_session_debug.add(DebugModel(
                            path=path_,
                            method=request.method,
                            ip=ip,
                            ram = ram,
                            ram_used=ram_used,
                            ram_total=ram_total,
                            ram_percent=ram_percent,
                            cpu=cpu,
                            time_execution=time_execution,
                            status_code=status_code, 
                            user_agent=user_agent 
                        ))
                        db_session_debug.commit()  
                    return response         

                except Exception as e:
                    message=str(e)
                    Logger.error(f"Error in DebugMiddleware: {message}")
                    print(f"Error in DebugMiddleware: {message}")
                    response = await call_next(request)
                    return response 
            response = await call_next(request)
            return response 
        else:
            response = await call_next(request)
            return response 
            
    def createTables(self):
        if DEBUG:
            if self.db is None:
                self.db = Database(config={"type":"sqlite","database":"debug.db"})
                self.db.connect()
                self.db_session = self.db.get_session() 
            else:
                inspector = inspect(self.db.engine)
                if inspector.has_table("debug") is False:
                    self.db.metadata.drop_all(self.db.engine)
                    self.db.migrate(use_base=True)      
 
 