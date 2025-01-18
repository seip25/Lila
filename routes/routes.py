from core.request import Request
from core.routing import Router
from core.templates import render,renderMarkdown
from core.session import Session
from core.responses import RedirectResponse
from middlewares.middlewares import login_required
from core.env import LANG_DEFAULT

#Example of routes

router = Router()

router.mount()

@router.route(path='/',methods=['GET'])
async def home(request : Request):
    response=render(request=request,template='index',files_translate=['guest'])
    return response

@router.route(path='/markdown',methods=['GET'])
async def home(request : Request):
    css=["/public/css/app.css"]
    response =renderMarkdown(request=request,file='test',css_files=css,picocss=True)
    return response

@router.route(path='/login',methods=['GET'])
async def login(request : Request):
    response =render(request=request,template='auth/login',files_translate=['guest'])
    return response

@router.route(path='/register',methods=['GET'])
async def login(request : Request):
    response =render(request=request,template='auth/register',files_translate=['guest'])
    return response

#Example middleware "login_required" (session web)
@router.route(path='/dashboard',methods=['GET'])
@login_required
async def dashboard(request: Request):
    response = render(request=request, template='auth/dashboard')
    return response

#Delete cookie for session
@router.route(path='/logout', methods=['GET'])
async def logout(request: Request) :
    response = RedirectResponse(url='/')
    response.delete_cookie("session")  
    response.delete_cookie("auth")    
    response.delete_cookie("admin")
    return response

#Change language (session)
@router.route(path='/set-language/{lang}',methods=['GET'])
async def set_language(request :Request):
    lang= request.path_params.get('lang',LANG_DEFAULT)
    if not lang:
        lang=request.query_params.get('lang',LANG_DEFAULT)

    referer= request.headers.get('Referer','/')
    response = RedirectResponse(url=referer)
    Session.setSession(name_cookie='lang',new_val=lang,response=response)
    return response

routes = router.get_routes()