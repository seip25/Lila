"""Jinja UI helpers: forms generated from Pydantic, pagination and small components.

All helpers return ``Markup`` with every value escaped. They are registered as
Jinja globals (``form``, ``pagination``, ``ui``) by ``lila.core.templates``.

    {{ form(UserCreate, action="/api/users", submit="Create", snackbar=True, redirect="/users") }}
    {{ pagination(page) }}                       {# page = await Model.paginate_async(...) #}
    {{ ui.input("email", "E-mail", type="email", required=True, error=errors.email) }}
    {{ ui.button("Save", variant="primary", type="submit") }}
    {{ ui.alert("Saved!", type="success", dismissible=True) }}
"""

from __future__ import annotations

import datetime as _dt
import decimal
import enum
import html
import secrets
import types
from typing import Any, Dict, Iterable, List, Literal, Optional, Union, get_args, get_origin
from urllib.parse import urlencode

from markupsafe import Markup

esc = html.escape

INPUT_CLASS = "input-lila w-full"
LABEL_CLASS = "block text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-1.5"
HELP_CLASS = "mt-1 text-xs text-slate-400"
ERROR_CLASS = "mt-1 text-xs font-medium text-red-600 dark:text-red-400"


def _attrs(values: Dict[str, Any]) -> str:
    """Renders HTML attributes: True -> bare attribute, False/None -> omitted,
    ``data_x`` -> ``data-x``."""
    parts = []
    for key, value in values.items():
        if value is None or value is False:
            continue
        name = str(key).rstrip("_").replace("_", "-")
        if value is True:
            parts.append(f" {name}")
        else:
            parts.append(f' {name}="{esc(str(value), quote=True)}"')
    return "".join(parts)


def _translate(text: Optional[str], trans: Optional[dict]) -> Optional[str]:
    if text and trans and text in trans:
        return trans[text]
    return text


def _label_text(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


# ──────────────────────────────────────────────────────────────────────────────
# Components
# ──────────────────────────────────────────────────────────────────────────────
class UI:
    """``{{ ui.input(...) }}``, ``{{ ui.button(...) }}``... (Tailwind classes included)."""

    def __init__(self, trans: Optional[dict] = None):
        self.trans = trans

    def _field(self, name, label, control, help=None, error=None, wrapper_class="") -> Markup:
        field_id = f"f-{name}"
        label_html = f'<label for="{esc(field_id)}" class="{LABEL_CLASS}">{esc(_translate(label, self.trans))}</label>' if label else ""
        help_html = f'<p class="{HELP_CLASS}">{esc(_translate(help, self.trans))}</p>' if help else ""
        error_html = (
            f'<p class="{ERROR_CLASS}" data-error-for="{esc(name)}">{esc(error)}</p>' if error
            else f'<p class="{ERROR_CLASS}" data-error-for="{esc(name)}" hidden></p>'
        )
        return Markup(f'<div class="{esc(wrapper_class)}">{label_html}{control}{help_html}{error_html}</div>')

    def input(self, name: str, label: Optional[str] = None, type: str = "text", value: Any = None,
              required: bool = False, help: Optional[str] = None, error: Optional[str] = None,
              placeholder: Optional[str] = None, wrapper_class: str = "", **attrs) -> Markup:
        css = attrs.pop("class_", None) or attrs.pop("css_class", None) or INPUT_CLASS
        control = (
            f'<input id="f-{esc(name)}" name="{esc(name)}"'
            + _attrs({"type": type, "value": None if value is None or type == "password" else value,
                      "required": required, "placeholder": _translate(placeholder, self.trans),
                      "aria-invalid": "true" if error else None, "class": css, **attrs})
            + ">"
        )
        return self._field(name, label, control, help, error, wrapper_class)

    def textarea(self, name: str, label: Optional[str] = None, value: Any = None, required: bool = False,
                 help: Optional[str] = None, error: Optional[str] = None, rows: int = 4,
                 wrapper_class: str = "", **attrs) -> Markup:
        css = attrs.pop("class_", None) or INPUT_CLASS
        control = (
            f'<textarea id="f-{esc(name)}" name="{esc(name)}"'
            + _attrs({"rows": rows, "required": required, "class": css, **attrs})
            + f">{esc('' if value is None else str(value))}</textarea>"
        )
        return self._field(name, label, control, help, error, wrapper_class)

    def select(self, name: str, options: Any, label: Optional[str] = None, value: Any = None,
               required: bool = False, help: Optional[str] = None, error: Optional[str] = None,
               placeholder: Optional[str] = None, wrapper_class: str = "", **attrs) -> Markup:
        css = attrs.pop("class_", None) or INPUT_CLASS
        items = options.items() if isinstance(options, dict) else [
            (o, o) if not isinstance(o, (tuple, list)) else (o[0], o[1]) for o in options
        ]
        opts = []
        if placeholder:
            opts.append(f'<option value="">{esc(_translate(placeholder, self.trans))}</option>')
        for key, text in items:
            selected = " selected" if value is not None and str(key) == str(value) else ""
            opts.append(f'<option value="{esc(str(key))}"{selected}>{esc(str(_translate(str(text), self.trans)))}</option>')
        control = (
            f'<select id="f-{esc(name)}" name="{esc(name)}"'
            + _attrs({"required": required, "class": css, **attrs}) + ">" + "".join(opts) + "</select>"
        )
        return self._field(name, label, control, help, error, wrapper_class)

    def checkbox(self, name: str, label: Optional[str] = None, checked: bool = False, value: str = "1",
                 unchecked: Optional[str] = "0", help: Optional[str] = None, error: Optional[str] = None,
                 **attrs) -> Markup:
        control = (
            f'<label class="inline-flex items-center gap-2 text-sm cursor-pointer">'
            f'<input type="checkbox" id="f-{esc(name)}" name="{esc(name)}"'
            + _attrs({"value": value, "checked": checked, "data-unchecked": unchecked,
                      "class": "w-4 h-4 accent-blue-600", **attrs})
            + f'> <span>{esc(_translate(label, self.trans) or "")}</span></label>'
        )
        return self._field(name, None, control, help, error)

    def button(self, text: str, variant: str = "primary", type: str = "button", **attrs) -> Markup:
        css = attrs.pop("class_", None) or f"btn btn-{variant}"
        return Markup(f"<button{_attrs({'type': type, 'class': css, **attrs})}>{esc(_translate(text, self.trans))}</button>")

    def link(self, text: str, href: str, variant: Optional[str] = None, **attrs) -> Markup:
        css = attrs.pop("class_", None) or (f"btn btn-{variant}" if variant else "text-blue-600 dark:text-blue-400 hover:underline")
        return Markup(f"<a{_attrs({'href': href, 'class': css, **attrs})}>{esc(_translate(text, self.trans))}</a>")

    _ALERT = {
        "success": "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-900 text-emerald-800 dark:text-emerald-200",
        "error": "bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-900 text-red-800 dark:text-red-200",
        "warning": "bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200",
        "info": "bg-blue-50 dark:bg-blue-950/40 border-blue-200 dark:border-blue-900 text-blue-800 dark:text-blue-200",
    }

    def alert(self, text: str, type: str = "info", dismissible: bool = False, **attrs) -> Markup:
        style = self._ALERT.get(type, self._ALERT["info"])
        close = '<button type="button" data-remove aria-label="Close" class="ml-3 opacity-60 hover:opacity-100">&times;</button>' if dismissible else ""
        role = "alert" if type in ("error", "warning") else "status"
        return Markup(
            f'<div role="{role}"{_attrs({"class": f"flex items-start justify-between rounded-xl border px-4 py-3 text-sm {style}", "data-removable": dismissible, **attrs})}>'
            f"<span>{esc(_translate(text, self.trans))}</span>{close}</div>"
        )

    _BADGE = {
        "gray": "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
        "blue": "bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300",
        "green": "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
        "red": "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300",
        "amber": "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
    }

    def badge(self, text: str, color: str = "gray") -> Markup:
        return Markup(f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold {self._BADGE.get(color, self._BADGE["gray"])}">{esc(_translate(text, self.trans))}</span>')

    def modal(self, id: str, title: str, body: Any = "", footer: Any = "") -> Markup:
        """``<dialog>`` opened with ``data-modal-target="#id"``, closed with ``data-close-modal``."""
        body_html = body if isinstance(body, Markup) else esc(str(body))
        footer_html = footer if isinstance(footer, Markup) else esc(str(footer))
        return Markup(
            f'<dialog id="{esc(id)}" class="m-auto rounded-2xl p-0 bg-surface dark:bg-surface-dark border border-slate-200 dark:border-slate-800 shadow-xl max-w-lg w-full backdrop:bg-slate-950/40">'
            f'<div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">'
            f'<h3 class="text-lg font-bold">{esc(_translate(title, self.trans))}</h3>'
            f'<button type="button" data-close-modal aria-label="Close" class="text-slate-400 hover:text-slate-600 text-xl">&times;</button></div>'
            f'<div class="px-6 py-4">{body_html}</div>'
            + (f'<div class="px-6 py-4 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2">{footer_html}</div>' if footer else "")
            + "</dialog>"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Forms from Pydantic models
# ──────────────────────────────────────────────────────────────────────────────
def _unwrap(annotation: Any):
    """Returns (base_type, optional)."""
    optional = False
    origin = get_origin(annotation)
    if origin is Union or (hasattr(types, "UnionType") and origin is types.UnionType):
        members = [a for a in get_args(annotation) if a is not type(None)]
        optional = len(members) != len(get_args(annotation))
        if len(members) == 1:
            inner, _ = _unwrap(members[0])
            return inner, optional
    return annotation, optional


def _constraints(field) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for meta in getattr(field, "metadata", []) or []:
        for attr, key in (("min_length", "minlength"), ("max_length", "maxlength"), ("ge", "min"), ("le", "max"),
                          ("gt", "gt"), ("lt", "lt"), ("pattern", "pattern"), ("multiple_of", "step")):
            value = getattr(meta, attr, None)
            if value is not None:
                out[key] = value
    if "gt" in out:
        out.setdefault("min", out.pop("gt"))
    if "lt" in out:
        out.setdefault("max", out.pop("lt"))
    return out


def field_widget(name: str, field) -> Dict[str, Any]:
    """Describes the HTML control for a Pydantic field (used by ``form()``)."""
    annotation, optional = _unwrap(field.annotation)
    type_name = getattr(annotation, "__name__", str(annotation))
    extra = field.json_schema_extra if isinstance(field.json_schema_extra, dict) else {}
    ui_opts = dict(extra.get("ui", {})) if isinstance(extra.get("ui"), dict) else {}
    widget: Dict[str, Any] = {"name": name, "control": "input", "type": "text", "attrs": _constraints(field)}

    origin = get_origin(annotation)
    if origin is Literal:
        widget.update(control="select", options=[(v, v) for v in get_args(annotation)])
    elif isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        widget.update(control="select", options=[(m.value, m.name.replace("_", " ").title()) for m in annotation])
    elif annotation is bool:
        widget.update(control="checkbox")
    elif annotation is int:
        widget["type"] = "number"
        widget["attrs"].setdefault("step", 1)
    elif annotation in (float, decimal.Decimal):
        widget["type"] = "number"
        widget["attrs"].setdefault("step", "any")
    elif annotation is _dt.datetime:
        widget["type"] = "datetime-local"
    elif annotation is _dt.date:
        widget["type"] = "date"
    elif annotation is _dt.time:
        widget["type"] = "time"
    elif "Email" in type_name:
        widget["type"] = "email"
    elif "Url" in type_name:
        widget["type"] = "url"
    elif "Secret" in type_name or "password" in name.lower():
        widget["type"] = "password"
    elif name.lower() in ("phone", "tel", "telephone"):
        widget["type"] = "tel"
    if ui_opts.get("widget") == "textarea":
        widget["control"] = "textarea"
    elif ui_opts.get("widget") == "hidden":
        widget.update(control="input", type="hidden")
    elif ui_opts.get("type"):
        widget["type"] = ui_opts["type"]
    widget["label"] = ui_opts.get("label") or field.title or _label_text(name)
    widget["help"] = ui_opts.get("help") or field.description
    widget["placeholder"] = ui_opts.get("placeholder")
    widget["required"] = bool(field.is_required()) and not optional and widget["control"] != "checkbox"
    widget["optional"] = optional
    if ui_opts.get("match"):
        widget["attrs"]["data-match"] = ui_opts["match"]
    try:
        default = field.get_default(call_default_factory=True)
    except TypeError:
        default = field.get_default()
    from pydantic_core import PydanticUndefined

    widget["default"] = None if default is PydanticUndefined else default
    return widget


def render_form(
    model: Any,
    action: str = "",
    method: str = "post",
    values: Optional[Dict[str, Any]] = None,
    errors: Optional[Dict[str, str]] = None,
    submit: str = "Save",
    fields: Optional[Iterable[str]] = None,
    exclude: Iterable[str] = (),
    id: Optional[str] = None,
    snackbar: bool = False,
    toast: Optional[str] = None,
    redirect: Optional[str] = None,
    reset: Any = False,
    target: Optional[str] = None,
    message: bool = True,
    columns: int = 1,
    attrs: Optional[Dict[str, Any]] = None,
    csrf_input: str = "",
    trans: Optional[dict] = None,
) -> Markup:
    """``<form data-lila-form>`` whose inputs mirror the Pydantic validation rules."""
    ui = UI(trans)
    values = dict(values or {})
    errors = dict(errors or {})
    model_fields = getattr(model, "model_fields", {})
    names: List[str] = list(fields) if fields else list(model_fields.keys())
    skip = set(exclude or ())
    parts: List[str] = []
    for name in names:
        if name in skip or name not in model_fields:
            continue
        w = field_widget(name, model_fields[name])
        value = values.get(name, w["default"])
        if isinstance(value, enum.Enum):
            value = value.value
        common = dict(label=w["label"], help=w["help"], error=errors.get(name))
        if w["control"] == "select":
            parts.append(ui.select(name, w["options"], value=value, required=w["required"],
                                   placeholder=w["placeholder"] or ("—" if w["optional"] else None), **common, **w["attrs"]))
        elif w["control"] == "checkbox":
            parts.append(ui.checkbox(name, w["label"], checked=bool(value), help=w["help"], error=errors.get(name)))
        elif w["control"] == "textarea":
            parts.append(ui.textarea(name, value=value, required=w["required"], **common, **w["attrs"]))
        elif w["type"] == "hidden":
            parts.append(Markup(f'<input type="hidden" name="{esc(name)}"{_attrs({"value": value})}>'))
        else:
            if isinstance(value, (_dt.date, _dt.datetime, _dt.time)):
                value = value.isoformat(timespec="minutes") if isinstance(value, _dt.datetime) else value.isoformat()
            parts.append(ui.input(name, type=w["type"], value=value, required=w["required"],
                                  placeholder=w["placeholder"], **common, **w["attrs"]))
    form_attrs = {
        "id": id or f"form-{secrets.token_hex(3)}",
        "action": action or None,
        "method": "get" if method.lower() == "get" else "post",
        "data-method": method.upper() if method.lower() not in ("get", "post") else None,
        "data-lila-form": True,
        "data-snackbar": snackbar,
        "data-toast": toast,
        "data-redirect": redirect,
        "data-reset": reset if isinstance(reset, str) else bool(reset),
        "data-target": target,
        "class": "space-y-4",
        **(attrs or {}),
    }
    grid = f'<div class="grid grid-cols-1 md:grid-cols-{int(columns)} gap-4">' if columns > 1 else "<div class=\"space-y-4\">"
    msg = '<div data-message hidden></div>' if message else ""
    button = ui.button(submit, type="submit", **{"data-loading-text": "..."})
    return Markup(f"<form{_attrs(form_attrs)}>{csrf_input}{grid}{''.join(parts)}</div>{msg}<div>{button}</div></form>")


# ──────────────────────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────────────────────
def render_pagination(page: Dict[str, Any], request: Any = None, param: str = "page", window: int = 2,
                      trans: Optional[dict] = None) -> Markup:
    """Links for a ``paginate_async()`` result; keeps the other query parameters."""
    if not page or int(page.get("pages", 1)) <= 1:
        return Markup("")
    current = int(page.get("page", 1))
    pages = int(page.get("pages", 1))
    query = dict(request.query_params) if request is not None and hasattr(request, "query_params") else {}
    path = request.url.path if request is not None and hasattr(request, "url") else ""

    def href(n: int) -> str:
        query[param] = str(n)
        return f"{path}?{urlencode(query)}"

    base = "min-w-9 h-9 px-3 inline-flex items-center justify-center rounded-lg text-sm font-semibold border transition"
    normal = f"{base} border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800"
    active = f"{base} bg-blue-600 border-blue-600 text-white"
    disabled = f"{base} border-slate-100 dark:border-slate-800 text-slate-300 dark:text-slate-600 pointer-events-none"

    items = []
    prev_label = esc((trans or {}).get("previous", "Previous") if trans and "previous" in trans else "Previous")
    next_label = esc((trans or {}).get("next", "Next") if trans and "next" in trans else "Next")
    if current > 1:
        items.append(f'<a href="{esc(href(current - 1))}" class="{normal}" rel="prev" aria-label="{prev_label}">&lsaquo;</a>')
    else:
        items.append(f'<span class="{disabled}" aria-hidden="true">&lsaquo;</span>')
    shown = sorted({1, pages, *range(max(1, current - window), min(pages, current + window) + 1)})
    last = 0
    for n in shown:
        if n - last > 1:
            items.append('<span class="px-1 text-slate-400">…</span>')
        if n == current:
            items.append(f'<span class="{active}" aria-current="page">{n}</span>')
        else:
            items.append(f'<a href="{esc(href(n))}" class="{normal}">{n}</a>')
        last = n
    if current < pages:
        items.append(f'<a href="{esc(href(current + 1))}" class="{normal}" rel="next" aria-label="{next_label}">&rsaquo;</a>')
    else:
        items.append(f'<span class="{disabled}" aria-hidden="true">&rsaquo;</span>')
    return Markup(f'<nav class="flex flex-wrap items-center justify-center gap-1.5 py-4" aria-label="Pagination">{"".join(items)}</nav>')
