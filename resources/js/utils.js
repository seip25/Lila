async function Http(url = "/", method = "GET", body = false, bodyForm = false, headers = {},) {
  const options = { method: method, headers: headers, credentials: "include", }; if (body) options["body"] = JSON.stringify(body); if (bodyForm) options["body"] = bodyForm; const response = await fetch(url, options); if (!response.ok) { const error = await response.json(); throw new Error(error.message || "Error fetch"); }
  const resp = await response.json(); return resp;
}
function getUrlParameter(name) { return new URLSearchParams(window.location.search).get(name); }
function theme(theme_ = false) {
  let theme = theme_ ? theme_ : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; if (theme_) { localStorage.setItem("theme", theme_); }
  if (localStorage.getItem("theme") === "dark" || localStorage.getItem("theme") === "light") { theme = localStorage.getItem("theme"); }
  document.documentElement.setAttribute("data-theme", theme); return theme;
}
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => { theme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",); }); document.addEventListener("DOMContentLoaded", () => { theme(); }); function lang(l = "es") { return (document.documentElement.lang === l || document.documentElement.lang.startsWith("es")); }

class ResponsiveDataTable {
  constructor(containerId, options = {}) { this.container = document.getElementById(containerId); if (!this.container) return; this.defaults = { data: [], columns: [], rowsPerPage: 10, search: true, pagination: true, headerTitles: {}, summaryFields: ["id"], edit: false, delete: false, breakpoint: 768, }; this.options = { ...this.defaults, ...options }; this.currentPage = 1; this.filteredData = [...this.options.data]; this.isMobile = window.innerWidth < this.options.breakpoint; this.init(); window.addEventListener("resize", () => this.handleResize()); }
  init() { this.renderContainer(); this.updateTable(); if (this.options.search) this.setupSearch(); }
  handleResize() { const wasMobile = this.isMobile; this.isMobile = window.innerWidth < this.options.breakpoint; if (wasMobile !== this.isMobile) this.updateTable(); }
  renderContainer() {
    this.container.innerHTML = `
      <section class="w-full">
        ${this.options.search
        ? `<div class="mb-6 flex items-center justify-between"><input type="search" class="datatable-search-input w-full max-w-xs px-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-205 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary text-sm transition-all text-slate-800 dark:text-slate-100" placeholder="${lang() ? "Buscar..." : "Search..."}" aria-label="Search"/></div>`
        : ""
      }

        <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800/80">
          <table class="datatable-table min-w-full divide-y divide-slate-100 dark:divide-slate-850 text-sm hidden"></table>
          <div class="datatable-mobile"></div>
        </div>

        ${this.options.pagination ? `<nav class="datatable-pagination mt-6 flex items-center justify-center gap-1.5" aria-label="Pagination"></nav>` : ""}
      </section>`;
  }
  renderTable() { const table = this.container.querySelector(".datatable-table"); const mobileView = this.container.querySelector(".datatable-mobile"); if (this.isMobile) { table.classList.add("hidden"); mobileView.classList.remove("hidden"); this.renderMobileView(); } else { table.classList.remove("hidden"); mobileView.classList.add("hidden"); this.renderDesktopTable(); } }
  renderDesktopTable() {
    const table = this.container.querySelector(".datatable-table"); table.innerHTML = `
      <thead>
        <tr class="datatable-header"></tr>
      </thead>
      <tbody class="datatable-body divide-y divide-slate-100 dark:divide-slate-850"></tbody>`; const headerRow = table.querySelector("thead tr"); this.options.columns.forEach((column) => { const th = document.createElement("th"); th.scope = "col"; th.className = "px-6 py-3.5 text-left text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800"; th.textContent = this.options.headerTitles[column.key] || column.title || column.key; headerRow.appendChild(th); }); if (this.options.edit || this.options.delete) { const th = document.createElement("th"); th.scope = "col"; th.className = "px-6 py-3.5 text-left text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800"; th.textContent = lang() ? "Acciones" : "Actions"; headerRow.appendChild(th); }
    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage; const endIndex = startIndex + this.options.rowsPerPage; const paginatedData = this.filteredData.slice(startIndex, endIndex); const tbody = table.querySelector("tbody"); paginatedData.forEach((item) => {
      const row = document.createElement("tr"); row.className = "hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors"; this.options.columns.forEach((column) => {
        const td = document.createElement("td"); td.className = "px-6 py-4 text-slate-700 dark:text-slate-300 whitespace-nowrap align-middle font-medium"; const value = item[column.key]; if (value && typeof value === "string" && /<[a-z][\s\S]*>/i.test(value)) { td.innerHTML = value; } else { td.textContent = value || "-"; }
        row.appendChild(td);
      }); if (this.options.edit || this.options.delete) {
        const td = document.createElement("td"); td.className = "px-6 py-4 whitespace-nowrap align-middle"; const actionsDiv = document.createElement("div"); actionsDiv.className = "flex items-center gap-2"; if (this.options.edit) { const btn = document.createElement("button"); btn.className = "px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-primary hover:text-white rounded-lg text-xs font-bold border border-slate-200 dark:border-slate-700 hover:border-primary transition-all cursor-pointer"; btn.textContent = lang() ? "Editar" : "Edit"; btn.onclick = (e) => this.handleAction("edit", e, item); actionsDiv.appendChild(btn); }
        if (this.options.delete) { const btn = document.createElement("button"); btn.className = "px-3 py-1.5 bg-red-50 dark:bg-red-950/20 text-red-555 hover:bg-red-500 hover:text-white rounded-lg text-xs font-bold border border-transparent transition-all cursor-pointer"; btn.textContent = lang() ? "Eliminar" : "Delete"; btn.onclick = (e) => this.handleAction("delete", e, item); actionsDiv.appendChild(btn); }
        td.appendChild(actionsDiv); row.appendChild(td);
      }
      tbody.appendChild(row);
    });
  }
  renderMobileView() {
    const mobileView = this.container.querySelector(".datatable-mobile"); mobileView.innerHTML = ""; const startIndex = (this.currentPage - 1) * this.options.rowsPerPage; const endIndex = startIndex + this.options.rowsPerPage; const paginatedData = this.filteredData.slice(startIndex, endIndex); paginatedData.forEach((item) => {
      const card = document.createElement("article"); card.className = "mb-4 p-5 rounded-2xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col gap-4"; const summary = document.createElement("h3"); summary.className = "text-base font-black text-slate-850 dark:text-slate-100 border-b border-slate-250 dark:border-slate-800 pb-2 mb-2 flex items-center justify-between"; this.options.summaryFields.forEach((fieldKey) => { const value = item[fieldKey]; summary.innerHTML += `<span>${value || "-"}</span>`; }); card.appendChild(summary); const details = document.createElement("dl"); details.className = "grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs pb-2 border-b border-slate-200 dark:border-slate-800 mb-2"; this.options.columns.forEach((column) => {
        if (this.options.summaryFields.includes(column.key)) return; const dt = document.createElement("dt"); dt.className = "font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider"; dt.textContent = this.options.headerTitles[column.key] || column.title || column.key; const dd = document.createElement("dd"); dd.className = "text-slate-700 dark:text-slate-300 font-semibold text-right break-all"; const cellValue = item[column.key]; if (cellValue && typeof cellValue === "string" && /<[a-z][\s\S]*>/i.test(cellValue)) { dd.innerHTML = cellValue; } else { dd.textContent = cellValue || "-"; }
        details.appendChild(dt); details.appendChild(dd);
      }); card.appendChild(details); if (this.options.edit || this.options.delete) {
        const actions = document.createElement("div"); actions.className = "flex items-center gap-2 justify-end"; if (this.options.edit) { const btn = document.createElement("button"); btn.className = "px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-primary hover:text-white rounded-lg text-xs font-bold border border-slate-200 dark:border-slate-700 hover:border-primary transition-all cursor-pointer"; btn.textContent = lang() ? "Editar" : "Edit"; btn.onclick = (e) => this.handleAction("edit", e, item); actions.appendChild(btn); }
        if (this.options.delete) { const btn = document.createElement("button"); btn.className = "px-3 py-1.5 bg-red-50 dark:bg-red-950/20 text-red-555 hover:bg-red-500 hover:text-white rounded-lg text-xs font-bold border border-transparent transition-all cursor-pointer"; btn.textContent = lang() ? "Eliminar" : "Delete"; btn.onclick = (e) => this.handleAction("delete", e, item); actions.appendChild(btn); }
        card.appendChild(actions);
      }
      mobileView.appendChild(card);
    });
  }
  renderPagination() {
    const pagination = this.container.querySelector(".datatable-pagination"); if (!pagination || !this.options.pagination) return; pagination.innerHTML = ""; const pageCount = Math.ceil(this.filteredData.length / this.options.rowsPerPage,); if (pageCount <= 1) return;
    const btnClass = "px-3 py-1.5 rounded-lg text-xs font-black border transition-all cursor-pointer ";
    const activeBtnClass = btnClass + "bg-primary border-primary text-white hover:bg-primary-dark shadow-material";
    const inactiveBtnClass = btnClass + "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-350 hover:bg-slate-50 dark:hover:bg-slate-800";
    const disabledBtnClass = btnClass + "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-600 opacity-50 cursor-not-allowed";

    const prevButton = document.createElement("button"); prevButton.textContent = "«"; prevButton.className = this.currentPage === 1 ? disabledBtnClass : inactiveBtnClass; prevButton.disabled = this.currentPage === 1; prevButton.onclick = () => this.changePage(this.currentPage - 1); pagination.appendChild(prevButton); const maxVisible = 5; let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2)); let end = start + maxVisible - 1; if (end > pageCount) { end = pageCount; start = Math.max(1, end - maxVisible + 1); }
    if (start > 1) { const firstButton = document.createElement("button"); firstButton.className = inactiveBtnClass; firstButton.textContent = "1"; firstButton.onclick = () => this.changePage(1); pagination.appendChild(firstButton); if (start > 2) pagination.appendChild(this.createEllipsis()); }
    for (let i = start; i <= end; i++) { const button = document.createElement("button"); button.className = i === this.currentPage ? activeBtnClass : inactiveBtnClass; button.textContent = i; button.onclick = () => this.changePage(i); pagination.appendChild(button); }
    if (end < pageCount) { if (end < pageCount - 1) pagination.appendChild(this.createEllipsis()); const lastButton = document.createElement("button"); lastButton.className = inactiveBtnClass; lastButton.textContent = pageCount; lastButton.onclick = () => this.changePage(pageCount); pagination.appendChild(lastButton); }
    const nextButton = document.createElement("button"); nextButton.className = this.currentPage === pageCount ? disabledBtnClass : inactiveBtnClass; nextButton.textContent = "»"; nextButton.disabled = this.currentPage === pageCount; nextButton.onclick = () => this.changePage(this.currentPage + 1); pagination.appendChild(nextButton);
  }
  createEllipsis() { const span = document.createElement("span"); span.className = "text-slate-400 px-1"; span.textContent = "..."; return span; }
  changePage(page) { this.currentPage = page; this.updateTable(); }
  handleAction(type, event, item) { if (!this.options[type]) return; const callback = typeof this.options[type] === "function" ? this.options[type] : window[this.options[type]]; if (typeof callback === "function") callback(event, item.id || item); }
  setupSearch() { const searchInput = this.container.querySelector(".datatable-search-input"); if (!searchInput) return; searchInput.addEventListener("input", (e) => { const term = e.target.value.toLowerCase().trim(); this.filteredData = this.options.data.filter((item) => this.options.columns.some((column) => String(item[column.key] || "").toLowerCase().includes(term),),); this.currentPage = 1; this.updateTable(); }); }
  updateTable() { this.renderTable(); if (this.options.pagination) this.renderPagination(); }
  updateData(newData) { this.options.data = newData; this.filteredData = [...newData]; this.currentPage = 1; this.updateTable(); }
  updateColumns(newColumns) { this.options.columns = newColumns; this.updateTable(); }
}

function initDrawer() {
  document.querySelectorAll(".lila-drawer, .lila-drawer-overlay, .lila-drawer-toggle").forEach(el => el.remove());

  const mainEl = document.querySelector("main");
  const aside = mainEl ? mainEl.querySelector(":scope > aside") : null;
  if (!aside) return;

  const overlay = document.createElement("div");
  overlay.className = "lila-drawer-overlay fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 opacity-0 pointer-events-none transition-opacity duration-300";
  document.body.appendChild(overlay);

  const drawer = document.createElement("div");
  drawer.className = "lila-drawer fixed top-0 left-0 h-full w-64 bg-surface dark:bg-surface-dark border-r border-slate-200 dark:border-slate-800 shadow-material z-50 p-4 transform -translate-x-full transition-transform duration-300 overflow-y-auto";
  drawer.innerHTML = aside.innerHTML;
  document.body.appendChild(drawer);

  const toggle = document.createElement("button");
  toggle.className = "lila-drawer-toggle fixed bottom-4 right-4 z-40 p-3 bg-primary text-white rounded-full shadow-material hover:scale-105 transition-all text-xl cursor-pointer md:hidden flex items-center justify-center w-12 h-12";
  toggle.innerHTML = "☰";
  toggle.setAttribute("aria-label", "Toggle menu");

  const header = document.querySelector("header");
  if (header) {
    const nav = header.querySelector("nav");
    if (nav) {
      nav.insertBefore(toggle, nav.firstChild);
    } else {
      header.prepend(toggle);
    }
  } else {
    document.body.prepend(toggle);
  }

  function openDrawer() {
    drawer.classList.add("open");
    drawer.classList.remove("-translate-x-full");
    overlay.classList.add("open");
    overlay.classList.remove("opacity-0", "pointer-events-none");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    drawer.classList.remove("open");
    drawer.classList.add("-translate-x-full");
    overlay.classList.remove("open");
    overlay.classList.add("opacity-0", "pointer-events-none");
    document.body.style.overflow = "";
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    if (drawer.classList.contains("open")) {
      closeDrawer();
    } else {
      openDrawer();
    }
  });

  overlay.addEventListener("click", closeDrawer);

  drawer.addEventListener("click", function (e) {
    if (e.target.tagName === "A") {
      closeDrawer();
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(initDrawer, 100);
  });
} else {
  setTimeout(initDrawer, 100);
}

document.addEventListener("lila:navigation", function () {
  setTimeout(initDrawer, 100);
});

window.initDrawer = initDrawer;

function lila(component, options) {
  if (component === "snackbar") {
    snackbar(options);
  }
}
function snackbar(options) {
  let snackbar = document.getElementById("snackbar");

  if (!snackbar) {
    snackbar = document.createElement("div");
    snackbar.id = "snackbar";
    document.body.appendChild(snackbar);
  }

  snackbar.className = "fixed bottom-4 left-4 z-50 max-w-sm p-4 text-white rounded-xl shadow-material-lg transform translate-y-12 opacity-0 transition-all duration-300 flex items-center gap-2 font-bold text-sm pointer-events-none";

  if (options.type === "success") {
    snackbar.classList.add("bg-green-600");
  } else if (options.type === "error") {
    snackbar.classList.add("bg-red-500");
  } else if (options.type === "warning") {
    snackbar.classList.add("bg-amber-500");
  } else {
    snackbar.classList.add("bg-primary");
  }

  snackbar.textContent = options.message || "";
  
  setTimeout(() => {
    snackbar.classList.remove("translate-y-12", "opacity-0");
    snackbar.classList.add("translate-y-0", "opacity-100");
  }, 10);

  const duration = options.duration || 3000;
  if (snackbar.timeoutId) {
    clearTimeout(snackbar.timeoutId);
  }

  snackbar.timeoutId = setTimeout(function () {
    snackbar.classList.add("translate-y-12", "opacity-0");
    snackbar.classList.remove("translate-y-0", "opacity-100");
  }, duration);
}
window.ResponsiveDataTable = ResponsiveDataTable; 
window.Http = Http; 
window.getUrlParameter = getUrlParameter;
window.theme = theme;
window.snackbar = snackbar;
