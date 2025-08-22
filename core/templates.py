from starlette.templating import Jinja2Templates
from app.config import VERSION_PROJECT,TITLE_PROJECT
from app.helpers.helpers import theme,lang,translate as t
from core.request import Request
from core.responses import HTMLResponse ,JSONResponse
from app.helpers.helpers import lang
from app.config import PATH_TEMPLATES_HTML,PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
import markdown
import os
import traceback
import sys


templates = Jinja2Templates(directory=PATH_TEMPLATES_HTML)
 
def render(request:Request, template: str,context :dict ={},theme_ :bool= True,translate:bool = True,files_translate:list=[],lang_default:str=None,templates=templates):
    try:
        template = f"{template}.html"
        default_context = {
            'title'   :TITLE_PROJECT,
            'version' : VERSION_PROJECT
        }
        if theme_:
            default_context['theme']=theme(request=request)

        if translate:
            if lang_default:
                default_context['lang']=lang_default
            else:
                default_context['lang']=lang(request=request)
            default_context['translate']=t(file_name='translations',request=request,lang_default=lang_default)
            
            if len(files_translate) > 0:
                for file_name in files_translate:
                    add_translations=t(file_name=file_name,request=request,lang_default=lang_default)
                    default_context['translate'].update(add_translations)
        context.update(default_context)
        return templates.TemplateResponse(request=request,name=template,context=context)
    except Exception as e:
        
        exc_type, exc_value, exc_tb = sys.exc_info()
        
        error_info = {
            'error_type': exc_type.__name__,
            'error_message': str(e),
            'template': template,
            'traceback': traceback.format_exc()
        }
         
        if exc_tb:
            frame = exc_tb.tb_frame
            error_info['file'] = frame.f_code.co_filename
            error_info['line'] = exc_tb.tb_lineno
            error_info['function'] = frame.f_code.co_name

           
            
            Logger.error(f"Render error in {error_info['file']}:{error_info['line']} "
                        f"({error_info['function']}): {error_info['error_message']}")
        else:
            Logger.error(f"Render error: {error_info['error_message']}") 

        error_details = f"{error_info['error_type']}: {error_info['error_message']}"
        message=  "Error rendering template"
        print(f" {message} - {error_details}")
        return JSONResponse({
            "success": False, 
            "message":message,
            "error_details":error_details
        }, status_code=500)
    
def renderMarkdown(request,file : str , base_path:str =PATH_TEMPLATES_MARKDOWN,css_files : list = [],js_files:list=[],picocss : bool =True):
    file_path=os.path.join(base_path,f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse('<h5>404</h5><br/><p>Not found</p>')
    
    with open(file=file_path,mode="r",encoding="utf-8") as file:
        mark=file.read()
        html_markdown= markdown.markdown(mark)   
    
    lang_=lang(request)
    
    title=TITLE_PROJECT
    head='<!DOCTYPE html>\n'
    head+=f"<html lang='{lang_}'>\n"
    head+='<head>\n'
    head+='<meta charset="UTF-8">\n'
    head+='<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    head+='<meta name="color-scheme" content="light dark">\n'
    head+='<meta http-equiv="X-UA-Compatible" content="ie=edge">\n'
    head+=f"<title>{title}</title>\n"
    if  picocss:
       head+= '<link  rel="stylesheet"  href="/public/css/pico.css">'
    if css_files :
        for css in css_files:
            head+=f"<link rel='stylesheet' type='text/css' href='{css}' />\n"
    
    if js_files :
        for js in js_files:
            head+=f"<script src='{js}' ></script>\n"
    
    head+='</head>\n<body>\n'

 
    html=f"{head}<main class='container'>{html_markdown}</main></body>\n</html>"    
    
    return HTMLResponse(content=html)
