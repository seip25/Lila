from starlette.templating import Jinja2Templates
from core.env import VERSION_PROJECT,TITLE_PROJECT
from core.helpers import theme,lang,translate as t
from core.request import Request
from core.responses import HTMLResponse 
from core.helpers import lang
import markdown
import os

templates = Jinja2Templates(directory='templates')
 
def render(request:Request, template: str,context :dict ={},theme_ :bool= True,translate:bool = True,files_translate:list=[]):
    template = f"{template}.html"
    default_context = {
        'title'   :TITLE_PROJECT,
        'version' : VERSION_PROJECT
    }
    if theme_:
        default_context['theme']=theme()

    if translate:
        default_context['lang']=lang(request=request)
        default_context['translate']=t(file_name='translations',request=request)
        if len(files_translate) > 0:
            for file_name in files_translate:
                add_translations=t(file_name=file_name,request=request)
                default_context['translate'].update(add_translations)
    context.update(default_context)
    return templates.TemplateResponse(request=request,name=template,context=context)

def renderMarkdown(request,file : str , base_path:str ='templates/markdown/',css_files : list = [],js_files:list=[]):
    file_path=os.path.join(base_path,f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse('<h5>404</h5><br/><p>Not found</p>')
    
    lang_=lang(request)
    
    title=TITLE_PROJECT
    html='<!DOCTYPE html>\n'
    html+=f"<html lang='{lang_}'>\n"
    html+='<head>\n'
    html+='<meta charset="UTF-8">\n'
    html+='<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html+='<meta name="color-scheme" content="light dark">\n'
    html+='<meta http-equiv="X-UA-Compatible" content="ie=edge">\n'
    html+=f"<title>{title}</title>\n"
    
    if css_files :
        for css in css_files:
            html+=f"<link rel='stylesheet' type='text/css' href='{css}' />\n"
    
    if js_files :
        for js in js_files:
            html+=f"<script src='{js}' ></script>\n"
    
    html+='</head>\n<body>\n'

    with open(file=file_path,mode="r",encoding="utf-8") as file:
        html+=file.read()
    
    html+='</body>\n</html>'
    html= markdown.markdown(html)   
    
    return HTMLResponse(content=html)