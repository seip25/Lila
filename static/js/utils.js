// English: Example utils.js for fetch and cookies (get,post,put,etc and jwt token)
// Español: Ejemplo de utils.js para fetch y cookies (get,post,put,etc y token jwt).

// HTTP Request function
async function Http({
  url = "/",
  method = "GET",
  body = false,
  bodyForm = false,
  token_jwt = false,
  headers = {}
}) {
  const options = {
    method: method,
    headers: headers,
  };
  if (body) options["body"] = JSON.stringify(body);
  if (bodyForm) options["body"] = bodyForm;

  // JWT Token
  if (token_jwt) {
    const token = await getCookie({ name: "token" });
    options.headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Error fetch");
  }
  return await response.json();
}

// Cookie functions
function setCookie({ name = "token", value, days = 7, secure = false }) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  let cookieString = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
  if (secure) cookieString += "; Secure";
  document.cookie = cookieString;
}

function getCookie({ name }) {
  return document.cookie.split("; ").reduce((r, v) => {
    const parts = v.split("=");
    return parts[0] === name ? decodeURIComponent(parts[1]) : r;
  }, "");
}

function deleteCookie({ name }) {
  document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
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

// Modal system
const modal = {
  init: function () {
    document.querySelectorAll('[data-target]').forEach(trigger => {
      const modalId = trigger.getAttribute('data-target');
      const modal = document.getElementById(modalId);

      if (modal) {
        trigger.addEventListener('click', (e) => {
          e.preventDefault();
          this.toggleModal(modal);
        });
      }
    });

    document.addEventListener('click', (e) => {
      if (this.visibleModal && e.target === this.visibleModal) {
        this.closeModal(this.visibleModal);
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.visibleModal) {
        this.closeModal(this.visibleModal);
      }
    });
  },

  toggleModal: function (modal) {
    modal.hasAttribute('open') ? this.closeModal(modal) : this.openModal(modal);
  },

  openModal: function (modal) {
    modal.showModal();
    this.visibleModal = modal;
  },

  closeModal: function (modal) {
    modal.close();
    this.visibleModal = null;
  },

  modalAlert: function (message, type = 'info', autoClose = 3000) {
    const modalId = 'pico-alert-modal';
    let modal = document.getElementById(modalId);
    const acceptText = lang() ? "Aceptar" : "Accept";
    if (!modal) {

      modal = document.createElement('dialog');
      modal.id = modalId;
      modal.innerHTML = `
        <article>
          <h3 class='flex center'  id="alert-title"></h3>
          <p class='flex center' id="alert-message"></p>
          <footer>
            <button class='secondary w-full' id="alert-ok">${acceptText}</button>
          </footer>
        </article>
      `;
      document.body.appendChild(modal);

      modal.querySelector('#alert-ok').addEventListener('click', () => {
        modal.close();
      });
    }

    const title = modal.querySelector('#alert-title');
    const msg = modal.querySelector('#alert-message');

    title.textContent = type === "success" ? (lang() ? "Éxito" : "Success") :
      type === "error" ? (lang() ? "Error" : "Error") :
        type === "warning" ? (lang() ? "Advertencia" : "Warning") :
          (lang() ? "Información" : "Information");
    title.className = `flex center text-${type}`;
    msg.textContent = message;

    modal.showModal();

    if (autoClose > 0) {
      setTimeout(() => {
        if (modal.hasAttribute('open')) {
          modal.close();
        }
      }, autoClose);
    }
  }
};

// Alert shortcuts
function alertSuccess(message = false) {
  modal.modalAlert(message || (lang() ? "Operación exitosa" : "Operation successful"), 'success', 3000);
}

function alertError(message = '') {
  modal.modalAlert(message || (lang() ? "Ha ocurrido un error" : "An error occurred"), 'error');
}

function alertWarning(message = false) {
  modal.modalAlert(message || (lang() ? "Advertencia" : "Warning"), 'warning', 3000);
}
function alertInfo(message = false) {
  modal.modalAlert(message || (lang() ? "Información" : "Information"), 'info', 3000);
}

// Loading overlay
let loadingOverlay;
function showLoading(title = lang() ? "Cargando..." : "Loading...") {
  if (!loadingOverlay) {
    loadingOverlay = document.createElement('div');
    loadingOverlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0,0,0,0.7);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 1000;
    `;

    loadingOverlay.innerHTML = `
      <article style="padding: 2rem; text-align: center;">
        <div style="
          width: 3rem;
          height: 3rem;
          border: 4px solid #fff;
          border-top-color: #0066cc;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        "></div>
        <p>${title}</p>
      </article>
      <style>
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      </style>
    `;

    document.body.appendChild(loadingOverlay);
    document.body.style.overflow = 'hidden';
  }
}

function hideLoading() {
  if (loadingOverlay) {
    loadingOverlay.remove();
    loadingOverlay = null;
    document.body.style.overflow = '';
  }
}

// Confirm dialog
function Confirm(title = '', message = '', type = 'warning', showCancel = true) {
  return new Promise((resolve) => {
    const modalId = 'pico-confirm-modal';
    let modal = document.getElementById(modalId);

    const cancelText = lang() ? "Cancelar" : "Cancel";
    const confirmText = lang() ? "Confirmar" : "Confirm";

    if (!modal) {
      modal = document.createElement('dialog');
      modal.id = modalId;
      document.body.appendChild(modal);
    }

    modal.innerHTML = `
      <article>
        <h3>${title || (lang() ? "¿Estás seguro?" : "Are you sure?")}</h3>
        <p>${message}</p>
        <footer>
          ${showCancel ? `<button id="confirm-cancel" class="secondary">${cancelText}</button>` : ''}
          <button id="confirm-ok">${confirmText}</button>
        </footer>
      </article>
    `;

    modal.querySelector('#confirm-ok').addEventListener('click', () => {
      modal.close();
      resolve(true);
    });

    if (showCancel) {
      modal.querySelector('#confirm-cancel').addEventListener('click', () => {
        modal.close();
        resolve(false);
      });
    }

    modal.showModal();
  });
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
      breakpoint: 768
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
      <div class="container">
        ${this.options.search ? `
          <div class="search-container">
            <input type="search" class="datatable-search-input" 
                   placeholder="${lang() ? 'Buscar...' : 'Search...'}"
                   aria-label="Search">
          </div>` : ''}

        <div class="table-responsive">
          <table class="table datatable-table"></table>
          <div class="datatable-mobile"></div>
        </div>

        ${this.options.pagination ? `
          <nav class="pagination datatable-pagination" aria-label="Pagination"></nav>` : ''}
      </div>`;
  }

  renderTable() {
    const table = this.container.querySelector('.datatable-table');
    const mobileView = this.container.querySelector('.datatable-mobile');

    if (this.isMobile) {
      table.style.display = 'none';
      mobileView.style.display = 'block';
      this.renderMobileView();
    } else {
      table.style.display = 'table';
      mobileView.style.display = 'none';
      this.renderDesktopTable();
    }
  }

  renderDesktopTable() {
    const table = this.container.querySelector('.datatable-table');
    table.innerHTML = `
      <thead class="datatable-header"></thead>
      <tbody class="datatable-body"></tbody>`;

    const headerRow = document.createElement('tr');
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

    table.querySelector('thead').appendChild(headerRow);

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const endIndex = startIndex + this.options.rowsPerPage;
    const paginatedData = this.filteredData.slice(startIndex, endIndex);

    const tbody = table.querySelector('tbody');
    paginatedData.forEach(item => {
      const row = document.createElement('tr');
      
      this.options.columns.forEach(column => {
        const td = document.createElement('td');
        td.textContent = item[column.key] || '-';
        row.appendChild(td);
      });

      if (this.options.edit || this.options.delete) {
        const td = document.createElement('td');
        td.style.display = 'flex';
        td.style.gap = '0.5rem';
        
        if (this.options.edit) {
          const btn = document.createElement('button');
          btn.className = 'secondary';
          btn.textContent = lang() ? 'Editar' : 'Edit';
          btn.onclick = () => this.handleAction('edit', item);
          td.appendChild(btn);
        }
        
        if (this.options.delete) {
          const btn = document.createElement('button');
          btn.className = 'secondary outline';
          btn.textContent = lang() ? 'Eliminar' : 'Delete';
          btn.onclick = () => this.handleAction('delete', item);
          td.appendChild(btn);
        }
        
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
      card.className = 'card';

      const summary = document.createElement('div');
      summary.className = 'font-bold';
      
      this.options.summaryFields.forEach(fieldKey => {
        const value = item[fieldKey] || '-';
        summary.innerHTML += `${value}<br>`;
      });
      
      card.appendChild(summary);

      const details = document.createElement('div');
      this.options.columns.forEach(column => {
        if (this.options.summaryFields.includes(column.key)) return;
        
        const row = document.createElement('div');
        row.className = 'grid';
        
        const label = document.createElement('span');
        label.className = 'text-muted';
        label.textContent = `${this.options.headerTitles[column.key] || column.title || column.key}:`;
        
        const value = document.createElement('span');
        value.textContent = item[column.key] || '-';
        
        row.appendChild(label);
        row.appendChild(value);
        details.appendChild(row);
      });
      
      card.appendChild(details);

      if (this.options.edit || this.options.delete) {
        const actions = document.createElement('div');
        actions.style.marginTop = '1rem';
        actions.style.display = 'flex';
        actions.style.gap = '0.5rem';
        
        if (this.options.edit) {
          const btn = document.createElement('button');
          btn.className = 'secondary';
          btn.textContent = lang() ? 'Editar' : 'Edit';
          btn.onclick = () => this.handleAction('edit', item);
          actions.appendChild(btn);
        }
        
        if (this.options.delete) {
          const btn = document.createElement('button');
          btn.className = 'secondary outline';
          btn.textContent = lang() ? 'Eliminar' : 'Delete';
          btn.onclick = () => this.handleAction('delete', item);
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
    prevButton.className = 'secondary';
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
      firstButton.className = 'secondary';
      firstButton.textContent = '1';
      firstButton.onclick = () => this.changePage(1);
      pagination.appendChild(firstButton);

      if (start > 2) pagination.appendChild(this.createEllipsis());
    }

    for (let i = start; i <= end; i++) {
      const button = document.createElement('button');
      button.className = i === this.currentPage ? 'active' : 'secondary';
      button.textContent = i;
      button.onclick = () => this.changePage(i);
      pagination.appendChild(button);
    }

    if (end < pageCount) {
      if (end < pageCount - 1) pagination.appendChild(this.createEllipsis());

      const lastButton = document.createElement('button');
      lastButton.className = 'secondary';
      lastButton.textContent = pageCount;
      lastButton.onclick = () => this.changePage(pageCount);
      pagination.appendChild(lastButton);
    }

    const nextButton = document.createElement('button');
    nextButton.className = 'secondary';
    nextButton.disabled = this.currentPage === pageCount;
    nextButton.innerHTML = '&raquo;';
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

  handleAction(type, item) {
    const callback = typeof this.options[type] === 'function' 
      ? this.options[type] 
      : window[this.options[type]];
    if (typeof callback === 'function') callback(item.id || item);
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
window.setCookie = setCookie;
window.getCookie = getCookie;
window.deleteCookie = deleteCookie;
window.getUrlParameter = getUrlParameter;
window.theme = theme;
window.alertSuccess = alertSuccess;
window.alertError = alertError;
window.alertWarning = alertWarning;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.Confirm = Confirm;