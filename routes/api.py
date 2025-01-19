from core.request import Request
from core.responses import JSONResponse
from core.routing import Router
from core.helpers import translate
from pydantic import EmailStr,BaseModel

#Json Responses
router=Router()

@router.route(path='/api',methods=['GET','POST'])
async def api(request : Request):
     return JSONResponse({'api':True})

#Example Pydantic
class LoginModel(BaseModel):
    email : EmailStr
    password: str

@router.route(path='/login',methods=['POST'],model=LoginModel)
async def login(request:Request):
    """Login function"""  
    msg= translate(file_name='guest',request=request)
    msg_error=msg['Incorrect email or password']
    body = await request.json()
    try:
        input=LoginModel(**body)
    except Exception as e:
        return JSONResponse({"success":False,"msg":f"Invalid JSON Body: {e}"},status_code=400)
    email = input.email
    password = input.password 
    response=JSONResponse({"success":False,"email":email,"password":password,"msg":msg_error})
    return response



#Example Pydantic
class RegisterModel(BaseModel):
    email : EmailStr
    password: str
    name :str
    password_2 :str

@router.route(path='/register',methods=['POST'],model=RegisterModel)
async def register(request:Request):
    """Register function""" 
    body = await request.json()
    try:
        input=RegisterModel(**body)
    except Exception as e:
        return JSONResponse({"success":False,"msg":f"Invalid JSON Body: {e}"},status_code=400)
    
    name=input.name
    email = input.email
    password = input.password 
    password_2=input.password_2
    response=JSONResponse({"success":True,"email":email,"password":password,"name":name,"password_2":password_2})
    return response
      
router.swagger_ui()

router.openapi_json()

routes=router.get_routes()