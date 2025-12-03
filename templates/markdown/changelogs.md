# {{ translate["changelogs"] }}

## 8.1

### {{ translate["cli_model"] }}

{{ translate["description_cli_model"] }}

**{{ translate["usage_example_cli_model"] }}:**

```html
python -m cli.model create --name Product --table products
```

{{ translate["list_models"] }}

**{{ translate["usage_example_cli_model"] }}:**

```html
python -m cli.model list-models
```

## 8.0

### {{ translate["asset_optimization"] }}

{{ translate["asset_optimization_desc"] }}

#### {{ translate["optimized_images"] }}

{{ translate["optimized_images_desc"] }}

**{{ translate["usage_example"] }}:**

```html
<link rel="stylesheet" href="{{ public('css/lila.css') }}" />
<img src="{{ image('img/lila.png') }}" alt="Lila" width="100" height="100" />
```

{{ translate["image_function_desc"] }}

#### {{ translate["automatic_css_minification"] }}

{{ translate["automatic_css_minification_desc"] }}

{{ translate["public_function_desc"] }}

---

## 0.7.2

### {{ translate["create_panel_admin"] }}

- {{ translate["create_panel_admin_desc"] }}
- python -m cli.create_panel_admin --password mypassword

### {{ translate["create_admin"] }}

- {{ translate["create_admin_desc"] }}
- python -m cli.create_admin --password mypassword

### {{ translate["pydantic_v2"] }}

- {{ translate["pydantic_v2_desc"] }}

### {{ translate["starlette_latest"] }}

- {{ translate["starlette_latest_desc"] }}

### {{ translate["psycopg2_latest"] }}

- {{ translate["psycopg2_latest_desc"] }}

### {{ translate["rest_crud_generate_html"] }}

- {{ translate["rest_crud_generate_html_desc"] }}
- `generate_html: bool = True`
- `rewrite_template: bool = False`  
  -url: {model_sql}\view

### {{ translate["Minify_CLI"] }}

- {{ translate["We've improved the CLI for minifying"] }}

### {{ translate["Compress HTML"] }}

- {{ translate["now always compress response html  and always and minifyin"] }}
