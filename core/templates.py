from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT
from core.translate import Translate
from core.request import Request
from core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from core.logger import Logger
import markdown
import os
import traceback
import sys
import orjson
import uuid
import html
import json

PROJECT_ROOT = os.getcwd()

jinja_env = Environment(
    loader=minify_loader(
        FileSystemLoader(PATH_TEMPLATES_HTML),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    ),
    auto_reload=DEBUG,
    autoescape=True,
)

MANIFEST_BUILD: dict[str, str] = {}

def react(component: str, props: dict = None) -> str:
    """
    Generates a mounting point for a React component with serialized props.
    """
    if props is None:
        props = {}
    id_ = 'react-' + uuid.uuid4().hex
    props_json = orjson.dumps(props).decode().replace('"', '&quot;')
    return f'<div id="{id_}" data-react-component="{component}" data-props="{props_json}"></div>'
MANIFEST_BUILD: dict[str, str] = {}
_VITE_PROJECT_EXISTS: bool = None

def get_vite_assets_data() -> dict:
    """
    Returns structured Vite assets data for SPA responses.
    """
    global _VITE_PROJECT_EXISTS
    data = {'scripts': [], 'css': []}
    if DEBUG:
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))

        if _VITE_PROJECT_EXISTS:
            data['scripts'].append({'src': 'http://localhost:5173/public/build/@vite/client', 'type': 'module'})
            data['scripts'].append({
                'content': '''
                    import RefreshRuntime from "http://localhost:5173/public/build/@react-refresh";
                    RefreshRuntime.injectIntoGlobalHook(window);
                    window.$RefreshReg$ = () => {};
                    window.$RefreshSig$ = () => (type) => type;
                    window.__vite_plugin_react_preamble_installed__ = true;
                ''',
                'type': 'module'
            })
            data['scripts'].append({'src': 'http://localhost:5173/public/build/resources/js/main.jsx', 'type': 'module'})
        return data
    global MANIFEST_BUILD
    if not MANIFEST_BUILD:
        try:
            from app.build_manifest import manifest
            MANIFEST_BUILD = manifest
        except ImportError:
            return data

    entry = MANIFEST_BUILD.get("file")
    css = MANIFEST_BUILD.get("css", [])
    
    if entry:
        data['scripts'].append({'src': f'/build/{entry}', 'type': 'module'})
    for css_file in css:
        data['css'].append(f'/build/{css_file}')
        
    return data

def is_frontend_request(request: Request) -> bool:
    """
    Check if the current request is a frontend SPA request.
    """
    return request.query_params.get('source') == 'frontend' or request.headers.get('x-lila-spa') == 'true'

def render_json_response(body: str, context: dict) -> JSONResponse:
    """
    Render a JSON response for SPA navigation.
    """
    seo_data = context.get("seo", {})
    response_data = {
        "meta": {
            "title": seo_data.get("title", context.get("title", TITLE_PROJECT)),
            "description": seo_data.get("description", context.get("description", DESCRIPTION_DEFAULT)),
            "keywords": seo_data.get("keywords", context.get("keywords", KEYWORDS_DEFAULT)),
            "author": context.get("author", AUTHOR_DEFAULT)
        },
        "lang": context.get("lang", LANG_DEFAULT),
        "scripts": context.get("scripts_array", []),
        "css": context.get("styles_array", []),
        "fonts": [],
        "body": body,
        "props": context.get("props_array", {}),
        "translations": context.get("translate", {})
    }
    return JSONResponse(response_data)

def renderReact(request: Request, component: str, props: dict = None, options: dict = None):
    """
    Renders a base HTML template configured to initialize a React component.
    """
    if props is None:
        props = {}
    if options is None:
        options = {}
    meta = options.get('meta', [])
    scripts = options.get('scripts', [])
    styles = options.get('styles', [])
    
    # English: Merge manual options into request SEO state if provided.
    # Español: Fusionar opciones manuales en el estado SEO de la petición si se proporcionan.
    if hasattr(request.state, "seo"):
        request.state.seo.update({
            "title": options.get("title", request.state.seo.get("title")),
            "description": options.get("description", request.state.seo.get("description")),
            "keywords": options.get("keywords", request.state.seo.get("keywords")),
        })
    else:
        request.state.seo = {
            "title": options.get("title", TITLE_PROJECT),
            "description": options.get("description", DESCRIPTION_DEFAULT),
            "keywords": options.get("keywords", KEYWORDS_DEFAULT),
        }

    meta_tags = '\n'.join([f'<meta name="{m["name"]}" content="{m["content"]}">' for m in meta])
    style_tags = '\n'.join([f'<link rel="stylesheet" href="{s}">' for s in styles])
    script_tags = '\n'.join([f'<script src="{s}"></script>' for s in scripts])
    
    context = {
        "component": component,
        "props": orjson.dumps(props).decode(),
        "seo": request.state.seo,
        "title": request.state.seo.get('title', TITLE_PROJECT),
        "keywords": request.state.seo.get('keywords', KEYWORDS_DEFAULT),
        "description": request.state.seo.get('description', DESCRIPTION_DEFAULT),
        "author": options.get('author', AUTHOR_DEFAULT),
        "lang": options.get('lang', LANG_DEFAULT),
        "head": f"{meta_tags}\n{style_tags}\n{script_tags}",
        "scripts_array": scripts,
        "styles_array": styles,
        "props_array": props,
        "translate": Translate.get_translations("translations", request, lang_default=options.get('lang'))
    }

    if is_frontend_request(request):
        vite_assets_data = get_vite_assets_data()
        context["scripts_array"].extend(vite_assets_data["scripts"])
        context["styles_array"].extend(vite_assets_data["css"])

        props_json = html.escape(orjson.dumps(props).decode())
        body = f'<div id="root" data-react-page="{component}" data-props=\'{props_json}\'></div>'
        return render_json_response(body, context)

    return render(request=request, template="lila/react_base", context=context)

def hot_reload() -> str:
    """
    Returns Vite hot reload scripts if DEBUG is True.
    """
    global _VITE_PROJECT_EXISTS
    if DEBUG:
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
            
        if _VITE_PROJECT_EXISTS:
            return """
            <script type="module">
                import RefreshRuntime from "http://localhost:5173/public/build/@react-refresh";
                RefreshRuntime.injectIntoGlobalHook(window);
            window.$RefreshReg$ = () => {};
            window.$RefreshSig$ = () => (type) => type;
            window.__vite_plugin_react_preamble_installed__ = true;
        </script>
        <script type="module" src="http://localhost:5173/public/build/@vite/client"></script>
        """
    return ""

def vite_assets() -> str:
    """
    Resolves Vite asset tags for production (manifest).
    In development, it should be used alongside hot_reload().
    """
    global _VITE_PROJECT_EXISTS
    if DEBUG:
        if _VITE_PROJECT_EXISTS is None:
            _VITE_PROJECT_EXISTS = os.path.exists(os.path.join(PROJECT_ROOT, "package-lock.json"))
            
        if _VITE_PROJECT_EXISTS:
            return '<script type="module" src="http://localhost:5173/public/build/resources/js/main.jsx"></script>'
        return ""
    
    global MANIFEST_BUILD
    if not MANIFEST_BUILD:
        try:
            from app.build_manifest import manifest
            MANIFEST_BUILD = manifest
        except ImportError:
            return ""

    entry = MANIFEST_BUILD.get("file")
    css = MANIFEST_BUILD.get("css", [])
    
    if not entry:
        return ""

    html_parts = [f'<script type="module" src="/build/{entry}"></script>']
    for css_file in css:
        html_parts.append(f'<link rel="stylesheet" href="/build/{css_file}">')
        
    return "\n".join(html_parts)

jinja_env.globals['react'] = react
jinja_env.globals['vite_assets'] = vite_assets
jinja_env.globals['hot_reload'] = hot_reload

ASSETS_MANIFEST: dict = {}
_assets_manifest_loaded: bool = False

def _load_assets_manifest():
    global ASSETS_MANIFEST, _assets_manifest_loaded
    if not _assets_manifest_loaded:
        manifest_path = os.path.join(PROJECT_ROOT, "app", "assets_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    ASSETS_MANIFEST = json.load(f)
            except Exception as e:
                Logger.warning(f"Error loading assets_manifest.json: {e}")
        _assets_manifest_loaded = True

def public(path: str) -> str:
    """
    Returns the URL path for a public asset.
    Checks the RAM manifest for optimized versions (.webp, .min.css, .min.js).
    """
    if not DEBUG:
        _load_assets_manifest()
        
    # English: Look up in the dictionary. If found, replace path.
    # Español: Buscar en el diccionario. Si existe, reemplazar la ruta.
    lookup_path = path.lstrip('/')
    if ASSETS_MANIFEST and lookup_path in ASSETS_MANIFEST:
        path = ASSETS_MANIFEST[lookup_path]
        
    if path.startswith('/'):
        return path
    return f"/{path}"

jinja_env.globals['public'] = public

templates = Jinja2Templates(env=jinja_env)
markdown_templates = Jinja2Templates(directory=PATH_TEMPLATES_MARKDOWN)
def get_base_context(request: Request, files_translate: list[str] = None, lang_default: str = None) -> dict:
    """
    Constructs the standard context dictionary for all template renders.
    """
    if files_translate is None:
        files_translate = []

    current_lang = lang_default if lang_default else Translate.lang(request)
    translations = Translate.get_translations("translations", request, lang_default=lang_default)

    for file_name in files_translate:
        translations.update(Translate.get_translations(file_name, request, lang_default=lang_default))

    seo_data = getattr(request.state, "seo", {})

    return {
        "title": seo_data.get("title", TITLE_PROJECT),
        "description": seo_data.get("description", DESCRIPTION_DEFAULT),
        "keywords": seo_data.get("keywords", KEYWORDS_DEFAULT),
        "seo": seo_data,
        "version": VERSION_PROJECT,
        "lang": current_lang,
        "translate": translations,
        "author": AUTHOR_DEFAULT,
    }


def render(request: Request, template: str, context: dict = None, files_translate: list[str] = None, lang_default: str = None,extension:str="html"):
    """
    Renders an HTML template with unified context and error handling.
    """
    if context is None:
        context = {}
    if files_translate is None:
        files_translate = []
    try:
        full_context = get_base_context(request, files_translate, lang_default)
        full_context.update(context)

        if is_frontend_request(request):
            full_context["layout"] = "lila/empty.html"
            full_context["request"] = request
            template_obj = jinja_env.get_template(f"{template}.{extension}")
            body = template_obj.render(full_context)

            return render_json_response(body, full_context)

        template_obj = jinja_env.get_template(f"{template}.{extension}")
        body = template_obj.render(full_context)
        return HTMLResponse(content=body)
    except Exception as e:
        return handle_render_error(template, e)

def handle_render_error(template: str, e: Exception):
    """
    Logs and formats template rendering errors based on the debug environment.
    """
    exc_type, _, exc_tb = sys.exc_info()
    tb_str = traceback.format_exc()
    error_name = exc_type.__name__ if exc_type else "Error"
    
    Logger.error(f"Render error in {template}: {str(e)}")
    print(f"\n{'='*20} TEMPLATE ERROR: {template} {'='*20}\n{tb_str}")

    if DEBUG:
        return HTMLResponse(content=f"<h1>{error_name}</h1><pre>{tb_str}</pre>", status_code=500)
    return JSONResponse({"success": False, "message": "Internal server error"}, status_code=500)

def renderMarkdown(request: Request, file: str, css_files: list = None, js_files: list = None, lang_default: str = None, translate_files: list[str] = None):
    """
    Converts a markdown file to HTML and wraps it in a layout template.
    """
    if css_files is None:
        css_files = []
    if js_files is None:
        js_files = []
    if translate_files is None:
        translate_files = []
    file_path = os.path.join(PATH_TEMPLATES_MARKDOWN, f"{file}.md")
    if not os.path.exists(file_path):
        return HTMLResponse("<h5>404</h5><p>Not found</p>", status_code=404)

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    context = get_base_context(request, translate_files, lang_default)
     
    import re
    def replace_translate(match):
        key = match.group(1)
        return str(context["translate"].get(key, match.group(0)))
    
    md_content = re.sub(r'\{\{\s*translate\["([^"]+)"\]\s*\}\}', replace_translate, md_content)

    html_content = markdown.markdown(md_content)
    context.update({
        "request": request,
        "content": html_content,
        "css_files": css_files,
        "js_files": js_files,
    })

    return markdown_templates.TemplateResponse("layout.html", context)
