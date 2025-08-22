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
    credentiasl:'include'
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
  return document.documentElement.lang === l;
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
      <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg">
        ${this.options.search ? `
          <div class="mb-4   "> 
            <input type="search" class="datatable-search-input w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" 
                    placeholder='${lang() ? 'Buscar' : 'Search'}'
                     aria-label="Search" />
          </div>` : ''}

        <div class="overflow-x-auto">
          <table class="table-auto w-full text-left datatable-table hidden"></table>
          <div class="datatable-mobile"></div>
        </div>

        ${this.options.pagination ? `
          <nav class="datatable-pagination mt-4 flex justify-center space-x-2" aria-label="Pagination"></nav>` : ''}
      </div>`;
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
      <thead class="bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200">
        <tr class="datatable-header"></tr>
      </thead>
      <tbody class="datatable-body divide-y divide-gray-200 dark:divide-gray-700"></tbody>`;

    const headerRow = table.querySelector('thead tr');
    this.options.columns.forEach(column => {
      const th = document.createElement('th');
      th.scope = 'col';
      th.className = 'px-6 py-3 text-sm font-semibold tracking-wider';
      th.textContent = this.options.headerTitles[column.key] || column.title || column.key;
      headerRow.appendChild(th);
    });

    if (this.options.edit || this.options.delete) {
      const th = document.createElement('th');
      th.scope = 'col';
      th.className = 'px-6 py-3 text-sm font-semibold tracking-wider';
      th.textContent = lang() ? 'Acciones' : 'Actions';
      headerRow.appendChild(th);
    }

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const endIndex = startIndex + this.options.rowsPerPage;
    const paginatedData = this.filteredData.slice(startIndex, endIndex);

    const tbody = table.querySelector('tbody');
    paginatedData.forEach(item => {
      const row = document.createElement('tr');
      row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors';

      this.options.columns.forEach(column => {
        const td = document.createElement('td');
        td.className = 'px-6 py-4 whitespace-nowrap text-sm';
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
        td.className = 'px-6 py-4 whitespace-nowrap text-right text-sm font-medium';
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'flex space-x-2 justify-end';

        if (this.options.edit) {
          const txt_edit = lang() ? 'Editar' : 'Edit';
          const btn = document.createElement('button');
          btn.className = 'text-indigo-600 hover:text-indigo-900 flex items-center group';
          btn.innerHTML = `
             <svg class="h-5 w-5 mr-1 text-indigo-500 group-hover:text-indigo-700 transition-colors" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
             </svg>
             <span>${txt_edit}</span>
          `;
          btn.onclick = (e) => this.handleAction('edit', e, item);
          actionsDiv.appendChild(btn);
        }

        if (this.options.delete) {
          const txt_delete = lang() ? 'Eliminar' : 'Delete';
          const btn = document.createElement('button');
          btn.className = 'text-red-600 hover:text-red-900 flex items-center group';
          btn.innerHTML = `
             <svg class="h-5 w-5 mr-1 text-red-500 group-hover:text-red-700 transition-colors" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
             </svg>
             <span>${txt_delete}</span>
          `;
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
      const card = document.createElement('div');
      card.className = 'bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-4';

      const summary = document.createElement('div');
      summary.className = 'font-bold text-lg mb-2 text-blue-600 dark:text-blue-400';

      this.options.summaryFields.forEach(fieldKey => {
        const value = item[fieldKey];
        if (value && typeof value === 'string' && /<[a-z][\s\S]*>/i.test(value)) {
          summary.innerHTML += `${value}<br>`;
        } else {
          summary.innerHTML += `${value || '-'}<br>`;
        }
      });

      card.appendChild(summary);

      const details = document.createElement('div');
      details.className = 'divide-y divide-gray-200 dark:divide-gray-700';
      this.options.columns.forEach(column => {
        if (this.options.summaryFields.includes(column.key)) return;

        const row = document.createElement('div');
        row.className = 'py-2 grid grid-cols-2 gap-4';

        const label = document.createElement('span');
        label.className = 'text-gray-500 font-medium dark:text-gray-400';
        label.textContent = `${this.options.headerTitles[column.key] || column.title || column.key}:`;

        const value = document.createElement('span');
        const cellValue = item[column.key];
        if (cellValue && typeof cellValue === 'string' && /<[a-z][\s\S]*>/i.test(cellValue)) {
          value.innerHTML = cellValue;
        } else {
          value.textContent = cellValue || '-';
        }

        row.appendChild(label);
        row.appendChild(value);
        details.appendChild(row);
      });

      card.appendChild(details);

      if (this.options.edit || this.options.delete) {
        const actions = document.createElement('div');
        actions.className = 'mt-4 flex space-x-2';

        if (this.options.edit) {
          const txt_edit = lang() ? 'Editar' : 'Edit';
          const btn = document.createElement('button');
          btn.className = 'bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md flex items-center space-x-1';
          btn.innerHTML = `
              <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
              </svg>
              <span>${txt_edit}</span>
          `;
          btn.onclick = (e) => this.handleAction('edit', e, item);
          actions.appendChild(btn);
        }

        if (this.options.delete) {
          const txt_delete = lang() ? 'Eliminar' : 'Delete';
          const btn = document.createElement('button');
          btn.className = 'bg-red-500 hover:bg-red-600 text-white font-bold py-2 px-4 rounded-md flex items-center space-x-1';
          btn.innerHTML = `
              <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 100 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
              </svg>
              <span>${txt_delete}</span>
          `;
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
    prevButton.className = `px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 dark:text-gray-100 dark:hover:bg-gray-700
                            hover:bg-gray-100 transition-colors ${this.currentPage === 1 ? 'opacity-50 cursor-not-allowed' : ''}`;
    prevButton.disabled = this.currentPage === 1;
    prevButton.innerHTML = '&laquo;';
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
      firstButton.className = 'px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors';
      firstButton.textContent = '1';
      firstButton.onclick = () => this.changePage(1);
      pagination.appendChild(firstButton);

      if (start > 2) pagination.appendChild(this.createEllipsis());
    }

    for (let i = start; i <= end; i++) {
      const button = document.createElement('button');
      button.className = i === this.currentPage
        ? 'px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white'
        : 'px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors';
      button.textContent = i;
      button.onclick = () => this.changePage(i);
      pagination.appendChild(button);
    }

    if (end < pageCount) {
      if (end < pageCount - 1) pagination.appendChild(this.createEllipsis());

      const lastButton = document.createElement('button');
      lastButton.className = 'px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors';
      lastButton.textContent = pageCount;
      lastButton.onclick = () => this.changePage(pageCount);
      pagination.appendChild(lastButton);
    }

    const nextButton = document.createElement('button');
    nextButton.className = `px-4 py-2 text-sm font-medium rounded-md border border-gray-300 dark:border-gray-600 dark:text-gray-100 dark:hover:bg-gray-700
                            hover:bg-gray-100 transition-colors ${this.currentPage === pageCount ? 'opacity-50 cursor-not-allowed' : ''}`;
    nextButton.disabled = this.currentPage === pageCount;
    nextButton.innerHTML = '&raquo;';
    nextButton.onclick = () => this.changePage(this.currentPage + 1);
    pagination.appendChild(nextButton);
  }

  createEllipsis() {
    const span = document.createElement('span');
    span.className = 'px-4 py-2 text-gray-500';
    span.textContent = '...';
    return span;
  }

  changePage(page) {
    this.currentPage = page;
    this.updateTable();
  }

  handleAction(type, event, item) {
    if (!this.options[type]) return;
    if (typeof this.options[type] === 'string' && !window[this.options[type]]) {
      console.error(`Callback function "${this.options[type]}" not found.`);
      return;
    }

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
      this.filteredData = this.options.data.filter(item => {
        return this.options.columns.some(column => {
          const value = item[column.key];
          return String(value).toLowerCase().includes(term);
        });
      });
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