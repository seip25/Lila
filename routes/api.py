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
class InputModel(BaseModel):
    email : EmailStr
    password: str

@router.route(path='/input',methods=['POST'])
async def login(request:Request):
    msg= translate(file_name='guest',request=request)
    msg_error=msg['Incorrect email or password']
    body = await request.json()
    input=InputModel(**body)
    email = input.email
    password = input.password 
    print(input)
    response=JSONResponse({"success":False,"email":email,"password":password,"msg":msg_error})
    return response
   
   


routes=router.get_routes()