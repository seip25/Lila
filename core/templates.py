from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG
from app.helpers.helpers import theme, lang, translate as t
from core.request import Request
from core.responses import HTMLResponse, JSONResponse
from app.helpers.helpers import lang
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
import markdown
import os
import traceback
import sys
from PIL import Image
from pathlib import Path
import rjsmin 
import rcssmin 

jinja_env = Environment(
    loader=minify_loader(
        FileSystemLoader(PATH_TEMPLATES_HTML),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    ),
    auto_reload=False,
    autoescape=True 
)

templates = Jinja2Templates( env=jinja_env)
 

def get_base_context(
    request: Request, files_translate: list[str] = [], lang_default: str = None
) -> dict:
    context = {
        "title": TITLE_PROJECT,
        "version": VERSION_PROJECT,
        "lang": lang_default if lang_default else lang(request),
        "translate": t("translations", request, lang_default=lang_default), 
        "image" :  image,
        "static" : public,
        "public" : public
    }

    for file_name in files_translate:
        context["translate"].update(t(file_name, request, lang_default=lang_default)) 
    return context


def render(
    request: Request,
    template: str,
    context: dict = {},
    files_translate: list[str] = [],
    lang_default: str = None,
    templates=templates,
):
    try:
        template_file = f"{template}.html"
        default_context = get_base_context(
            request=request, files_translate=files_translate, lang_default=lang_default
        )
        context.update(default_context)
        return templates.TemplateResponse(
            request=request, name=template_file, context=context
        )
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

        error_details = f"{type(e).__name__}: {str(e)}" 
        print(error_details)
        error_details = error_details if DEBUG else ""
        msg = "Error rendering template" if DEBUG else "General error"
        return JSONResponse(
            {"success": False, "message": msg,
             "error_details": error_details,
             "file": error_info['file'],
             "line": error_info['line'],
             "function": error_info['function'],
             "error_type": error_info['error_type'],
             "error_message": error_info['error_message'],
             "traceback": error_info['traceback']
             },
            status_code=500,
        )
 
markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)


def renderMarkdown(
    request: Request,
    file: str,
    css_files: list = [],
    js_files: list = [], 
    lang_default: str = None,
    translate_files: list[str] = [],
):
    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        not_found_path = os.path.join(PATH_TEMPLATES_HTML, "404.html")
        if os.path.exists(not_found_path):
            return templates.TemplateResponse(
                request=request,
                name="404.html",
                context={"request": request},
                status_code=404,
            )
        else:
            return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    context_translate = t("translations", request, lang_default)
    for file_name in translate_files:
        context_translate.update(t(file_name, request, lang_default)) 

    for key, val in context_translate.items():
        md_content = md_content.replace(f'{{{{ translate["{key}"] }}}}', val)

    html_content = markdown.markdown(md_content)

    context = {
        "request": request,
        "content": html_content,
        "title": TITLE_PROJECT,
        "lang": lang_default if lang_default else lang(request), 
        "css_files": css_files,
        "js_files": js_files,
    }

    return markdown_templates.TemplateResponse("layout.html", context)


def image(file_path: str) -> str:
    extension = file_path.split(".")[-1].lower()
    file_path_webp = file_path.replace(f".{extension}", ".webp")
    if (os.path.exists(os.path.join("static",file_path_webp))==False):
        optimize_image(os.path.join("static",file_path))
    return f"/public/{file_path_webp}"


def optimize_image(file_path,  max_width=1920, quality=75) -> Path:
    if isinstance(file_path, str):
        file_path = Path(file_path)
    
    img = Image.open(file_path)
     

    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

    optimized_filename = f"{file_path.stem}.webp"
    optimized_path = file_path.parent / optimized_filename
    img.save(optimized_path, format="WEBP", optimize=True, quality=quality)

    return optimized_path

def public(file_path: str) -> str:
    new_file_path = file_path
    extension = file_path.split(".")[-1].lower()
    if (extension in [ "css","js"]):
        exists_min= os.path.exists(os.path.join("static",file_path.replace(f".{extension}", ".min.{extension}")))
        if (exists_min==False):
            with open(os.path.join("static",file_path), "r", encoding="utf-8") as f:
                content = f.read()
            if (extension == "css"):
                minified_content = rcssmin.cssmin(content)
            else:
                minified_content = rjsmin.jsmin(content)
            with open(os.path.join("static",file_path.replace(f".{extension}", f".min.{extension}")), "w", encoding="utf-8") as f:
                f.write(minified_content)
            new_file_path = file_path.replace(f".{extension}", f".min.{extension}")
    if(extension in ["png", "jpg", "jpeg", "gif", "webp"]):
        optimize_image(os.path.join("static",file_path))
        new_file_path = file_path.replace(f".{extension}", ".webp")
    return f"/public/{new_file_path}"
