from starlette.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader
from jinja2_htmlmin import minify_loader
from app.config import VERSION_PROJECT, TITLE_PROJECT, DEBUG, DESCRIPTION_DEFAULT, KEYWORDS_DEFAULT, AUTHOR_DEFAULT, LANG_DEFAULT, MINIFY_HTML, APP_URL, HOST, PORT
from lila.core.translate import Translate
from lila.core.request import Request
from lila.core.responses import HTMLResponse, JSONResponse
from app.config import PATH_TEMPLATES_HTML, PATH_TEMPLATES_MARKDOWN
from lila.core.logger import Logger
import markdown
import os
import traceback
import sys
import json

PROJECT_ROOT = os.getcwd()

if MINIFY_HTML:
    loader = minify_loader(
        FileSystemLoader(PATH_TEMPLATES_HTML),
        remove_comments=True,
        remove_empty_space=True,
        remove_all_empty_space=True,
        reduce_boolean_attributes=True,
    )
else:
    loader = FileSystemLoader(PATH_TEMPLATES_HTML)

jinja_env = Environment(
    loader=loader,
    auto_reload=DEBUG,
    autoescape=True,
)

MANIFEST_BUILD: dict[str, str] = {}

_VITE_PROJECT_EXISTS: bool = None
STYLES_DEFAULT_TAILWIND: str = None

def hot_reload() -> str:
    return ""


jinja_env.globals['hot_reload'] = hot_reload

_VITE_MANIFEST: dict = {}
_vite_manifest_loaded: bool = False
ASSETS_MANIFEST: dict = {}
_assets_manifest_loaded: bool = False

def _load_vite_manifest():
    """
    English: Loads the Vite build assets manifest dynamically from public/.vite/manifest.json.
    Español: Carga dinámicamente el manifiesto de recursos de construcción de Vite desde public/.vite/manifest.json.
    """
    global _VITE_MANIFEST, _vite_manifest_loaded
    if not _vite_manifest_loaded:
        manifest_path = os.path.join(PROJECT_ROOT, "public", ".vite", "manifest.json")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(PROJECT_ROOT, "public", "manifest.json")
            
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    _VITE_MANIFEST = json.load(f)
            except Exception as e:
                Logger.warning(f"Error loading Vite manifest: {e}")
        _vite_manifest_loaded = True

def _load_assets_manifest():
    """
    English: Loads the classic static assets manifest.
    Español: Carga el manifiesto clásico de recursos estáticos.
    """
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

def public(path: str, force_static: bool = False) -> str:
    """
    Resolves the public URL for a given static asset.
    """
    clean_path = path.lstrip('/')
    resolved_path = f"/{clean_path}"
    
    _load_assets_manifest()
    if ASSETS_MANIFEST and clean_path in ASSETS_MANIFEST:
        path_val = ASSETS_MANIFEST[clean_path]
        resolved_path = path_val if path_val.startswith('/') else f"/{path_val}"
    
    if not DEBUG and APP_URL:
        return f"{APP_URL.rstrip('/')}{resolved_path}"
    return resolved_path

jinja_env.globals['public'] = public

def asset(path: str, force_static: bool = False) -> str:
    """
    Returns the complete HTML tag for a CSS or JS asset, or a simple URL string for other assets.
    If the path is 'css/tailwind.css', it returns the Tailwind CDN and Google Fonts configuration.
    """
    clean_path = path.lstrip('/')
    
    if clean_path == 'css/tailwind.css':
        return """
  <!-- Google Fonts for Outfit and Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <!-- Tailwind CSS Play CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            primary: 'var(--primary, #1a73e8)',
            'primary-dark': 'var(--primary-dark, #1557b0)',
            secondary: 'var(--secondary, #e91e63)',
            'secondary-dark': 'var(--secondary-dark, #c2185b)',
            accent: 'var(--accent, #ffc107)',
            surface: 'var(--surface, #ffffff)',
            'surface-dark': 'var(--surface-dark, #1e293b)',
            'bg-body': 'var(--bg-body, #f0f4f9)',
            'bg-body-dark': 'var(--bg-body-dark, #0f172a)',
            'lila-bg': 'var(--lila-bg, #f0f4f9)',
            'lila-surface': 'var(--lila-surface, #ffffff)',
            'lila-primary': 'var(--lila-primary, #1a73e8)',
            'lila-primary-hover': 'var(--lila-primary-hover, #1557b0)',
            'lila-sidebar': 'var(--lila-sidebar, #e9eef6)',
            'ai-blue': '#1A73E8',
            'ai-purple': '#A062FC',
            'ai-orange': '#FF6E6E',
            gemini: {
              blue: '#1a73e8',
              blueBg: '#f0f4f9',
              blueHover: '#e1ecf8',
              indigo: '#4f46e5',
              purple: '#8b5cf6',
              accent: '#4285f4',
              darkBg: '#090d16',
              darkCard: '#131b2e',
              darkBorder: '#1e293b',
              darkHover: '#1e293b'
            }
          },
          fontFamily: {
            sans: ['Inter', 'sans-serif'],
            heading: ['Outfit', 'sans-serif'],
          }
        }
      }
    }
  </script>
  
  <style type="text/tailwindcss">
    :root {
      --primary: #1a73e8;
      --primary-dark: #1557b0;
      --secondary: #e91e63;
      --secondary-dark: #c2185b;
      --accent: #ffc107;
      --surface: #ffffff;
      --surface-dark: #1e293b;
      --bg-body: #f0f4f9;
      --bg-body-dark: #0f172a;

      --lila-bg: #f0f4f9;
      --lila-surface: #ffffff;
      --lila-primary: #1a73e8;
      --lila-primary-hover: #1557b0;
      --lila-sidebar: #e9eef6;
      --shadow-material: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
      --shadow-material-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
      --shadow-lila-input: 0 8px 22px 0 rgba(0, 0, 0, 0.04), 0 2px 8px 0 rgba(0, 0, 0, 0.04);
      --shadow-lila-input-focus: 0 12px 40px 0 rgba(26, 115, 232, 0.12), 0 2px 12px 0 rgba(26, 115, 232, 0.06);
      --shadow-lila-card: 0 4px 24px 0 rgba(0, 0, 0, 0.03);
      --shadow-lila-card-hover: 0 12px 36px 0 rgba(0, 0, 0, 0.07);
    }

    :root[data-theme="dark"] {
      --bg-body: #131314;
      --bg-body-dark: #131314;
      --surface: #1e1f20;
      --surface-dark: #1e1f20;
      --primary: #a8c7fa;
      --lila-bg: #131314;
      --lila-surface: #1e1f20;
      --lila-primary: #a8c7fa;
      --lila-primary-hover: #7baaf7;
      --lila-sidebar: #1e1f20;
    }

    @layer components {
      .lila-card,
      .card {
        background-color: var(--lila-surface);
        border-radius: 24px;
        box-shadow: var(--shadow-lila-card);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(226, 232, 240, 0.3);
      }

      :root[data-theme="dark"] .lila-card,
      :root[data-theme="dark"] .card {
        border: 1px solid rgba(255, 255, 255, 0.04);
      }

      .text-lila {
        color: var(--lila-primary);
      }
      
      :root[data-theme="dark"] .text-lila {
        color: var(--lila-primary);
      }

      .lila-card:hover,
      .card:hover {
        box-shadow: var(--shadow-lila-card-hover);
      }

      .lila-link {
        background-color: transparent;
        color: var(--lila-primary);
        cursor: pointer;
        text-decoration: none;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      }

      .lila-link:hover {
        color: var(--lila-primary-hover);
      }

      .lila-btn,
      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 500;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        text-decoration: none;
      }

      .lila-btn-primary,
      .btn-primary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: var(--lila-primary);
        color: #ffffff;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        text-decoration: none;
      }

      :root[data-theme="dark"] .lila-btn-primary,
      :root[data-theme="dark"] .btn-primary {
        color: #131314;
      }

      .lila-btn-primary:hover,
      .btn-primary:hover {
        background-color: var(--lila-primary-hover);
        transform: scale(1.02);
        box-shadow: 0 4px 12px 0 rgba(26, 115, 232, 0.15);
      }

      :root[data-theme="dark"] .lila-btn-primary:hover,
      :root[data-theme="dark"] .btn-primary:hover {
        box-shadow: 0 4px 20px 0 rgba(168, 199, 250, 0.2);
      }

      .lila-btn-secondary,
      .btn-secondary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        background-color: var(--lila-surface);
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        text-decoration: none;
      }

      :root[data-theme="dark"] .lila-btn-secondary,
      :root[data-theme="dark"] .btn-secondary {
        color: #ffffff;
      }

      .lila-btn-outline,
      .btn-outline {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        background-color: transparent;
        border: 1px solid rgba(128, 128, 128, 0.3);
        text-decoration: none;
      }

      .lila-btn-outline:hover,
      .btn-outline:hover {
        background-color: rgba(26, 115, 232, 0.04);
        border-color: var(--lila-primary);
        transform: scale(1.02);
      }

      .btn-danger,
      .btn-error {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: #ef4444;
        color: #ffffff;
        text-decoration: none;
      }

      .btn-danger:hover,
      .btn-error:hover {
        background-color: #dc2626;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-danger,
      :root[data-theme="dark"] .btn-error {
        background-color: #f87171;
        color: #131314;
      }

      .btn-success {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: #10b981;
        color: #ffffff;
        text-decoration: none;
      }

      .btn-success:hover {
        background-color: #059669;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-success {
        background-color: #34d399;
        color: #131314;
      }

      .btn-warning {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: #f59e0b;
        color: #ffffff;
        text-decoration: none;
      }

      .btn-warning:hover {
        background-color: #d97706;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-warning {
        background-color: #fbbf24;
        color: #131314;
      }

      .btn-info {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: #06b6d4;
        color: #ffffff;
        text-decoration: none;
      }

      .btn-info:hover {
        background-color: #0891b2;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-info {
        background-color: #22d3ee;
        color: #131314;
      }

      .btn-light {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        color: #1e293b;
        text-decoration: none;
      }

      .btn-light:hover {
        background-color: #f1f5f9;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-light {
        background-color: #1e1f20;
        border-color: rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
      }

      .btn-dark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        border: none;
        background-color: #0f172a;
        color: #ffffff;
        border: none;
        text-decoration: none;
      }

      .btn-dark:hover {
        background-color: #1e293b;
        transform: scale(1.02);
      }

      :root[data-theme="dark"] .btn-dark {
        background-color: #ffffff;
        color: #0f172a;
      }

      .btn-outline-primary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        background-color: transparent;
        border: 1.5px solid var(--lila-primary);
        color: var(--lila-primary);
        text-decoration: none;
      }

      .btn-outline-primary:hover {
        background-color: var(--lila-primary);
        color: #ffffff;
        transform: scale(1.02);
        box-shadow: 0 4px 12px 0 rgba(26, 115, 232, 0.1);
      }

      :root[data-theme="dark"] .btn-outline-primary {
        border-color: #a8c7fa;
        color: #a8c7fa;
      }

      :root[data-theme="dark"] .btn-outline-primary:hover {
        background-color: #a8c7fa;
        color: #131314;
        box-shadow: 0 4px 20px 0 rgba(168, 199, 250, 0.15);
      }

      .btn-outline-secondary {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.75rem 1.75rem;
        font-weight: 600;
        border-radius: 9999px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        gap: 0.5rem;
        outline: none;
        background-color: transparent;
        border: 1.5px solid #e91e63;
        color: #e91e63;
        text-decoration: none;
      }

      .btn-outline-secondary:hover {
        background-color: #e91e63;
        color: #ffffff;
        transform: scale(1.02);
        box-shadow: 0 4px 12px 0 rgba(233, 30, 99, 0.1);
      }

      :root[data-theme="dark"] .btn-outline-secondary {
        border-color: #f06292;
        color: #f06292;
      }

      :root[data-theme="dark"] .btn-outline-secondary:hover {
        background-color: #f06292;
        color: #131314;
      }

      .form-control,
      .input-lila {
        width: 100%;
        padding: 0.9rem 1.5rem;
        background-color: var(--lila-surface);
        border-radius: 16px;
        box-shadow: var(--shadow-lila-input);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        border: 1px solid rgba(128, 128, 128, 0.25);
        outline: none;
        color: inherit;
      }

      :root[data-theme="dark"] .form-control,
      :root[data-theme="dark"] .input-lila {
        border-color: rgba(255, 255, 255, 0.06);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
        background-color: #131314;
      }

      .form-control:focus,
      .input-lila:focus {
        box-shadow: var(--shadow-lila-input-focus);
        border-color: rgba(26, 115, 232, 0.35);
        transform: translateY(-1px);
      }
    }
  </style>
        """
        
    resolved = public(clean_path, force_static=force_static)
    if clean_path.endswith('.css'):
        return f'<link rel="stylesheet" href="{resolved}" />'
        
    if clean_path.endswith('.js'):
        return f'<script src="{resolved}"></script>'
        
    return resolved

jinja_env.globals['asset'] = asset

def get_flashes(request: Request) -> list[dict]:
    """
    English: Returns queued flash messages and clears them so they aren't shown again.
    Español: Retorna los mensajes flash en cola y los limpia para que no se muestren de nuevo.
    """
    flashes = []
    if hasattr(request.state, "_flash_messages"):
        flashes.extend(request.state._flash_messages)
        request.state._flash_messages = []
    if hasattr(request.state, "_new_flashes"):
        flashes.extend(request.state._new_flashes)
        request.state._new_flashes = []
    return flashes


jinja_env.globals['get_flashes'] = get_flashes

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
        "author": seo_data.get("author", AUTHOR_DEFAULT),
        "app_url": APP_URL or f"http://{HOST}:{PORT}",
        "debug": DEBUG,
        "debug_html": getattr(request.app, "debug_html", False),
        "get_flashes": lambda: get_flashes(request),
    }


def render(request: Request, template: str, context: dict = None, files_translate: list[str] = None, lang_default: str = None,extension:str="jinja"):
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

    return markdown_templates.TemplateResponse(request, "layout.jinja", context)
