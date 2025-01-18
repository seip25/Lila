from starlette.applications import Starlette 

class App:
    def __init__(self, debug : bool =False,routes  = []):
        self.routes =routes
        self.debug = debug

    def start(self): 
        try:
            return Starlette(debug=self.debug,routes=self.routes)
        except RuntimeError as e:
            print(f"{e}")