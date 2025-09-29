from starlette.templating import Jinja2Templates
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


templates = Jinja2Templates(directory=PATH_TEMPLATES_HTML)


def get_base_context(
    request: Request, files_translate: list[str] = [], lang_default: str = None
) -> dict:
    context = {
        "title": TITLE_PROJECT,
        "version": VERSION_PROJECT,
        "lang": lang_default if lang_default else lang(request),
        "translate": t("translations", request, lang_default=lang_default),
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
        error_details = f"{type(e).__name__}: {str(e)}"
        Logger.error(f"Render error: {error_details}")
        print(error_details)
        error_details = error_details if DEBUG else ""
        msg = "Error rendering template" if DEBUG else "General error"
        return JSONResponse(
            {"success": False, "message": msg, "error_details": error_details},
            status_code=500,
        )


markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)


def renderMarkdown(
    request: Request,
    file: str,
    css_files: list = [],
    js_files: list = [],
    picocss: bool = False,
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
        print(context_translate)

    for key, val in context_translate.items():
        md_content = md_content.replace(f'{{{{ translate["{key}"] }}}}', val)

    html_content = markdown.markdown(md_content)

    context = {
        "request": request,
        "content": html_content,
        "title": TITLE_PROJECT,
        "lang": lang_default if lang_default else lang(request),
        "picocss": picocss,
        "css_files": css_files,
        "js_files": js_files,
    }

    return markdown_templates.TemplateResponse("layout.html", context)
