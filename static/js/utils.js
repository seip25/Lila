async function Http(
  url = "/",
  method = "GET",
  body = false,
  bodyForm = false,
  headers = {}
) {

  const options = {
    method: method,
    headers: headers,
    credentials: 'include'
  };
  if (body) options["body"] = JSON.stringify(body);
  if (bodyForm) options["body"] = bodyForm;


  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Error fetch");
  }
  const resp = await response.json();
  return resp;
}

// URL parameter function
function getUrlParameter(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function theme(theme_ = false) {
  let theme = theme_ ? theme_ : window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

  if (theme_) {
    localStorage.setItem('theme', theme_);
  }
  if (localStorage.getItem('theme') === 'dark' || localStorage.getItem('theme') === 'light') {
    theme = localStorage.getItem('theme');
  }
  document.documentElement.setAttribute('data-theme', theme)

  return theme;
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
  theme(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
})
document.addEventListener('DOMContentLoaded', () => {
  theme();
});
// Language helper
function lang(l = "es") {
  return document.documentElement.lang === l || document.documentElement.lang.startsWith("es");
}


class ResponsiveDataTable {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.defaults = {
      data: [],
      columns: [],
      rowsPerPage: 10,
      search: true,
      pagination: true,
      headerTitles: {},
      summaryFields: ['id'],
      edit: false,
      delete: false,
      breakpoint: 768,
    };

    this.options = { ...this.defaults, ...options };
    this.currentPage = 1;
    this.filteredData = [...this.options.data];
    this.isMobile = window.innerWidth < this.options.breakpoint;

    this.init();
    window.addEventListener('resize', () => this.handleResize());
  }

  init() {
    this.renderContainer();
    this.updateTable();
    if (this.options.search) this.setupSearch();
  }

  handleResize() {
    const wasMobile = this.isMobile;
    this.isMobile = window.innerWidth < this.options.breakpoint;
    if (wasMobile !== this.isMobile) this.updateTable();
  }

  renderContainer() {
    this.container.innerHTML = `
      <section>
        ${this.options.search ? `
        <header>
          <input type="search" class="datatable-search-input" placeholder="${lang() ? 'Buscar' : 'Search'}" aria-label="Search" />
        </header>` : ''}

        <div>
          <table class="datatable-table hidden"></table>
          <div class="datatable-mobile"></div>
        </div>

        ${this.options.pagination ? `<nav class="datatable-pagination mt flex gap-2" aria-label="Pagination"></nav>` : ''}
      </section>`;
  }

  renderTable() {
    const table = this.container.querySelector('.datatable-table');
    const mobileView = this.container.querySelector('.datatable-mobile');

    if (this.isMobile) {
      table.classList.add('hidden');
      mobileView.classList.remove('hidden');
      this.renderMobileView();
    } else {
      table.classList.remove('hidden');
      mobileView.classList.add('hidden');
      this.renderDesktopTable();
    }
  }

  renderDesktopTable() {
    const table = this.container.querySelector('.datatable-table');
    table.innerHTML = `
      <thead>
        <tr class="datatable-header"></tr>
      </thead>
      <tbody class="datatable-body"></tbody>`;

    const headerRow = table.querySelector('thead tr');
    this.options.columns.forEach(column => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = this.options.headerTitles[column.key] || column.title || column.key;
      headerRow.appendChild(th);
    });

    if (this.options.edit || this.options.delete) {
      const th = document.createElement('th');
      th.scope = 'col';
      th.textContent = lang() ? 'Acciones' : 'Actions';
      headerRow.appendChild(th);
    }

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const endIndex = startIndex + this.options.rowsPerPage;
    const paginatedData = this.filteredData.slice(startIndex, endIndex);

    const tbody = table.querySelector('tbody');
    paginatedData.forEach(item => {
      const row = document.createElement('tr');

      this.options.columns.forEach(column => {
        const td = document.createElement('td');
        const value = item[column.key];
        if (value && typeof value === 'string' && /<[a-z][\s\S]*>/i.test(value)) {
          td.innerHTML = value;
        } else {
          td.textContent = value || '-';
        }
        row.appendChild(td);
      });

      if (this.options.edit || this.options.delete) {
        const td = document.createElement('td');
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'mt flex justify-between gap-4';

        if (this.options.edit) {
          const btn = document.createElement('button');
          btn.className = 'outline';
          btn.textContent = lang() ? 'Editar' : 'Edit';
          btn.onclick = (e) => this.handleAction('edit', e, item);
          actionsDiv.appendChild(btn);
        }

        if (this.options.delete) {
          const btn = document.createElement('button');
          btn.textContent = lang() ? 'Eliminar' : 'Delete';
          btn.onclick = (e) => this.handleAction('delete', e, item);
          actionsDiv.appendChild(btn);
        }

        td.appendChild(actionsDiv);
        row.appendChild(td);
      }

      tbody.appendChild(row);
    });
  }

  renderMobileView() {
    const mobileView = this.container.querySelector('.datatable-mobile');
    mobileView.innerHTML = '';

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const endIndex = startIndex + this.options.rowsPerPage;
    const paginatedData = this.filteredData.slice(startIndex, endIndex);

    paginatedData.forEach(item => {
      const card = document.createElement('article');

      const summary = document.createElement('h3');
      this.options.summaryFields.forEach(fieldKey => {
        const value = item[fieldKey];
        summary.innerHTML += `${value || '-'}<br>`;
      });
      card.appendChild(summary);

      const details = document.createElement('dl');
      this.options.columns.forEach(column => {
        if (this.options.summaryFields.includes(column.key)) return;

        const dt = document.createElement('dt');
        dt.textContent = this.options.headerTitles[column.key] || column.title || column.key;

        const dd = document.createElement('dd');
        const cellValue = item[column.key];

        if (cellValue && typeof cellValue === 'string' && /<[a-z][\s\S]*>/i.test(cellValue)) {
          dd.innerHTML = cellValue;
        } else {
          dd.textContent = cellValue || '-';
        }

        details.appendChild(dt);
        details.appendChild(dd);
      });

      card.appendChild(details);

      if (this.options.edit || this.options.delete) {
        const actions = document.createElement('div');
        actions.className = 'mt flex justify-between gap-4';

        if (this.options.edit) {
          const btn = document.createElement('button');
          btn.className = 'outline';
          btn.textContent = lang() ? 'Editar' : 'Edit';
          btn.onclick = (e) => this.handleAction('edit', e, item);
          actions.appendChild(btn);
        }

        if (this.options.delete) {
          const btn = document.createElement('button');
          btn.textContent = lang() ? 'Eliminar' : 'Delete';
          btn.onclick = (e) => this.handleAction('delete', e, item);
          actions.appendChild(btn);
        }

        card.appendChild(actions);
      }

      mobileView.appendChild(card);
    });
  }

  renderPagination() {
    const pagination = this.container.querySelector('.datatable-pagination');
    if (!pagination || !this.options.pagination) return;

    pagination.innerHTML = '';
    const pageCount = Math.ceil(this.filteredData.length / this.options.rowsPerPage);
    if (pageCount <= 1) return;

    const prevButton = document.createElement('button');
    prevButton.textContent = '«';
    prevButton.className = 'fill';
    prevButton.disabled = this.currentPage === 1;
    prevButton.onclick = () => this.changePage(this.currentPage - 1);
    pagination.appendChild(prevButton);

    const maxVisible = 5;
    let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
    let end = start + maxVisible - 1;
    if (end > pageCount) {
      end = pageCount;
      start = Math.max(1, end - maxVisible + 1);
    }

    if (start > 1) {
      const firstButton = document.createElement('button');
      firstButton.textContent = '1';
      firstButton.onclick = () => this.changePage(1);
      pagination.appendChild(firstButton);

      if (start > 2) pagination.appendChild(this.createEllipsis());
    }

    for (let i = start; i <= end; i++) {
      const button = document.createElement('button');
      button.className = i === this.currentPage ? '' : 'fill';
      button.textContent = i;
      button.onclick = () => this.changePage(i);
      pagination.appendChild(button);
    }

    if (end < pageCount) {
      if (end < pageCount - 1) pagination.appendChild(this.createEllipsis());

      const lastButton = document.createElement('button');
      lastButton.textContent = pageCount;
      lastButton.onclick = () => this.changePage(pageCount);
      pagination.appendChild(lastButton);
    }

    const nextButton = document.createElement('button');
    nextButton.className = 'fill';
    nextButton.textContent = '»';
    nextButton.disabled = this.currentPage === pageCount;
    nextButton.onclick = () => this.changePage(this.currentPage + 1);
    pagination.appendChild(nextButton);
  }

  createEllipsis() {
    const span = document.createElement('span');
    span.textContent = '...';
    return span;
  }

  changePage(page) {
    this.currentPage = page;
    this.updateTable();
  }

  handleAction(type, event, item) {
    if (!this.options[type]) return;
    const callback = typeof this.options[type] === 'function'
      ? this.options[type]
      : window[this.options[type]];
    if (typeof callback === 'function') callback(event, item.id || item);
  }

  setupSearch() {
    const searchInput = this.container.querySelector('.datatable-search-input');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase().trim();
      this.filteredData = this.options.data.filter(item =>
        this.options.columns.some(column =>
          String(item[column.key] || '').toLowerCase().includes(term)
        )
      );
      this.currentPage = 1;
      this.updateTable();
    });
  }

  updateTable() {
    this.renderTable();
    if (this.options.pagination) this.renderPagination();
  }

  updateData(newData) {
    this.options.data = newData;
    this.filteredData = [...newData];
    this.currentPage = 1;
    this.updateTable();
  }

  updateColumns(newColumns) {
    this.options.columns = newColumns;
    this.updateTable();
  }
}


window.ResponsiveDataTable = ResponsiveDataTable;
window.Http = Http;
window.getUrlParameter = getUrlParameter;
window.theme = theme; 
