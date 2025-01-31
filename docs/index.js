const sections = [
    { id: "install-eng", name: "Installation (eng)" },
    { id: "routes-eng", name: "Routes (eng)" },
    { id: "models-eng", name: "Models  (eng)" },
    { id: "middlewares-eng", name: "Middlewares (eng)" },
    { id: "connections-eng", name: "Connections (eng)" },
    { id: "migrations-eng", name: "Migrations (eng)" },
    { id: "locales-eng", name: "Locales (eng)" },
    { id: "static-eng", name: "Static (eng)" },
    { id: "templates-eng", name: "Templates (eng)" },
    { id: "markdown-eng", name: "Markdown/HTML (eng)" },
    { id: "helpers-eng", name: "Helpers (eng)" },

    { id: "install-esp", name: "Installación (esp)" },
    { id: "routes-esp", name: "Rutas (esp)" },
    { id: "models-esp", name: "Modelos(esp)" },
    { id: "middlewares-esp", name: "Middlewares(esp)" },
    { id: "connections-esp", name: "Conexiones(esp)" },
    { id: "migrations-esp", name: "Migraciones(esp)" },
    { id: "locales-esp", name: "Locales(esp)" },
    { id: "static-esp", name: "Static(esp)" },
    { id: "templates-esp", name: "Templates(esp)" },
    { id: "markdown-esp", name: "Markdown/HTML(esp)" },
    { id: "helpers-esp", name: "Helpers(esp)" },
];

function searchDocs(event = false) {
    let query = event
        ? event.target.value.toLowerCase()
        : document.getElementById("searchBox").value.toLowerCase();
    let results = document.getElementById("searchResults");
    results.innerHTML = "";

    if (query.length > 0) {
        let filtered = sections.filter(s => s.name.toLowerCase().includes(query));
        filtered.forEach(s => {
            let li = document.createElement("li");
            let link = document.createElement("a");
            link.href = `#${s.id}`;
            link.textContent = s.name;
            li.appendChild(link);
            results.appendChild(li);
        });
    }
}
