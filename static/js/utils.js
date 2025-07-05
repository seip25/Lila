//English : Example utils.js for fetch and cookies (get,post,put,etc and  jwt token)
//Español: Ejemplo de utils.js para fetch y cookies (get,post,put,etc y token jwt).

// Ejemplo de búsqueda, para obtener el ID de usuario y el token , en el cliente(token de sesión, no jwt)
//  const token=await getCookie({name:'token'})
//  const resp=await fetch('/api/token',{ headers:{
//  'Authorization': 'Bearer '+token
//  }
//  })

// Example of fetch, to get the user ID and token, on the client (session token, not jwt)
// const token=await getCookie({name:'token'})
// const resp=await fetch('/api/token',{ headers:{
// 'Authorization': 'Bearer '+token
// }
// })
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

  //JWT Token
  if (token_jwt) {
    const token = await getCookie({ name: "token" });
    options.headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(url, options);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Error fetch");
  }
  const resp = await response.json();
  return resp;
}

function setCookie({ name = "token", value, days = 7, secure = false }) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  let cookieString = `${name}=${encodeURIComponent(
    value
  )}; expires=${expires}; path=/; SameSite=Lax`;
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

function getUrlParameter(name) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(name);
}

function applyTheme(theme) {
  const html = document.documentElement;

  html.classList.remove('light', 'dark');

  if (theme === 'system') {
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    html.classList.add(systemTheme);
    localStorage.setItem('theme', 'system');
  } else {
    html.classList.add(theme);
    localStorage.setItem('theme', theme);
  }
}

function initializeTheme() {
  const savedTheme = localStorage.getItem('theme');

  if (savedTheme) {
    applyTheme(savedTheme);
  }
  else {
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    applyTheme(systemTheme);
  }

  if (typeof modal !== 'undefined' && modal.init) {
    modal.init();
  }
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
  const savedTheme = localStorage.getItem('theme');

  if (savedTheme === 'system' || !savedTheme) {
    applyTheme(e.matches ? 'dark' : 'light');
  }
});

function toggleTheme(selectedTheme) {
  applyTheme(selectedTheme);
}



document.addEventListener('DOMContentLoaded', () => {
  modal.init();
  initializeTheme();
});

function lang(l = "es") {
  return document.querySelector('html').lang == l;
}

const modal = {
  animationDuration: 200,
  isOpenClass: 'modal-open',
  openingClass: 'modal-opening',
  closingClass: 'modal-closing',
  visibleModal: null,

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
    if (modal.open) {
      this.closeModal(modal);
    } else {
      this.openModal(modal);
    }
  },

  openModal: function (modalElement) {
    if (typeof modalElement.showModal === 'function') {
      document.documentElement.classList.add(this.isOpenClass, this.openingClass);
      modalElement.showModal();
      this.visibleModal = modalElement;
      setTimeout(() => {
        document.documentElement.classList.remove(this.openingClass);
      }, this.animationDuration);
    } else {
      if (document.getElementById(modalElement.id)) {
        AbrirModal(modalElement.id);
      }
    }
  },

  closeModal: function (modalElement) {
    if (typeof modalElement.close === 'function') {
      document.documentElement.classList.add(this.closingClass);
      setTimeout(() => {
        document.documentElement.classList.remove(this.closingClass, this.isOpenClass);
        modalElement.close();
        this.visibleModal = null;
      }, this.animationDuration);
    } else {
      if (document.getElementById(modalElement.id)) {
        CerrarModal(modalElement.id);
      }
    }
  },

  modalAlert: function (mensaje, tipo = 'info', tiempoCierre = 3000) {
    const alertModalId = 'tailwind-alert-modal';
    let alertModal = document.getElementById(alertModalId);
    const acceptText = lang() ? "Aceptar" : "Accept";

    const typeStyles = {
      success: { icon: 'check_circle', iconClass: 'text-green-500 dark:text-green-400', buttonClass: 'bg-green-600 hover:bg-green-700 focus-visible:outline-green-600' },
      error: { icon: 'error', iconClass: 'text-red-500 dark:text-red-400', buttonClass: 'bg-red-600 hover:bg-red-700 focus-visible:outline-red-600' },
      warning: { icon: 'warning', iconClass: 'text-yellow-500 dark:text-yellow-400', buttonClass: 'bg-yellow-500 hover:bg-yellow-600 focus-visible:outline-yellow-500' },
      info: { icon: 'info', iconClass: 'text-blue-500 dark:text-blue-400', buttonClass: 'bg-blue-600 hover:bg-blue-700 focus-visible:outline-blue-600' }
    };
    const currentStyle = typeStyles[tipo] || typeStyles.info;
    const titleText = tipo === "success" ? (lang() ? "Éxito" : "Success")
      : tipo === "error" ? (lang() ? "Error" : "Error")
        : tipo === "warning" ? (lang() ? "Advertencia" : "Warning")
          : (lang() ? "Información" : "Information");

    if (!alertModal) {
      alertModal = document.createElement('div');
      alertModal.id = alertModalId;
      alertModal.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4 opacity-0 transition-opacity duration-300';
      alertModal.setAttribute('role', 'dialog');
      alertModal.setAttribute('aria-modal', 'true');
      alertModal.setAttribute('aria-labelledby', 'alert-modal-title');

      alertModal.innerHTML = `
        <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity dark:bg-gray-900 dark:bg-opacity-80 alert-backdrop"></div>
        <div class="relative mx-auto w-full max-w-sm sm:max-w-md transform overflow-hidden rounded-xl bg-white dark:bg-gray-800 text-left shadow-2xl transition-all my-auto p-6">
          <div class="text-center">
            <span class="material-icons text-5xl ${currentStyle.iconClass} mx-auto alert-icon-content">${currentStyle.icon}</span>
            <h3 class="mt-3 text-2xl font-semibold leading-6 text-gray-900 dark:text-gray-100 alert-title-content" id="alert-modal-title">${titleText}</h3>
            <div class="mt-2">
              <p class="text-md text-gray-600 dark:text-gray-300 alert-message-content">${mensaje}</p>
            </div>
          </div>
          <div class="mt-6 sm:mt-8">
            <button type="button" class="inline-flex w-full justify-center rounded-md px-4 py-2.5 text-base font-semibold text-white shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 alert-ok-button ${currentStyle.buttonClass}">
              ${acceptText}
            </button>
          </div>
        </div>
      `;
      document.body.appendChild(alertModal);

      alertModal.querySelector('.alert-ok-button').addEventListener('click', () => CerrarModal(alertModalId));
      alertModal.querySelector('.alert-backdrop').addEventListener('click', () => CerrarModal(alertModalId));
    } else {
      alertModal.querySelector('.alert-icon-content').textContent = currentStyle.icon;
      alertModal.querySelector('.alert-icon-content').className = `material-icons text-5xl ${currentStyle.iconClass} mx-auto alert-icon-content`;
      alertModal.querySelector('.alert-title-content').textContent = titleText;
      alertModal.querySelector('.alert-message-content').textContent = mensaje;
      const okButton = alertModal.querySelector('.alert-ok-button');
      okButton.className = `inline-flex w-full justify-center rounded-md px-4 py-2.5 text-base font-semibold text-white shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 alert-ok-button ${currentStyle.buttonClass}`;
      okButton.textContent = acceptText;
    }

    AbrirModal(alertModalId);

    if (tiempoCierre > 0) {
      setTimeout(() => {
        const stillVisibleModal = document.getElementById(alertModalId);
        if (stillVisibleModal && !stillVisibleModal.classList.contains('hidden')) {
          CerrarModal(alertModalId);
        }
      }, tiempoCierre);
    }
  }
};



function AbrirModal(modalId) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) {
    modalElement.classList.remove('hidden');
    modalElement.classList.add('flex');
    requestAnimationFrame(() => {
      modalElement.classList.remove('opacity-0');
      modalElement.classList.add('opacity-100');
    });
    modal.visibleModal = modalElement;
    document.body.classList.add('overflow-hidden');
    const mainContentWrapper = document.querySelector('main') || document.body;

  }
}

function CerrarModal(modalId) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) {
    modalElement.classList.remove('opacity-100');
    modalElement.classList.add('opacity-0');
    setTimeout(() => {
      modalElement.classList.add('hidden');
      modalElement.classList.remove('flex');
    }, modal.animationDuration);
    modal.visibleModal = null;
    document.body.classList.remove('overflow-hidden');
    const mainContentWrapper = document.querySelector('main') || document.body;
    mainContentWrapper.classList.remove('backdrop-blur-sm');
  }
}

window.ShowModal = AbrirModal;
window.CloseModal = CerrarModal;

function alertSuccess(mensaje = false, titulo = 'Ok') {
  modal.modalAlert(mensaje || (lang() ? "Operación exitosa" : "Operation successful"), 'success', 3000);
}

function alertError(mensaje = '', titulo = 'Error', showConfirmButton = true) {
  modal.modalAlert(mensaje || (lang() ? "Ha ocurrido un error" : "An error occurred"), 'error', showConfirmButton ? 0 : 3000);
}

function alertWarning(mensaje = false, titulo = '') {
  modal.modalAlert(mensaje || (lang() ? "Advertencia" : "Warning"), 'warning', 3000);
}

let loadingOverlay;
function showLoading(title = lang() ? "Cargando..." : "Loading...") {
  if (!loadingOverlay) {
    loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.className = 'fixed inset-0 bg-gray-900 bg-opacity-75 flex items-center justify-center z-[101] transition-opacity duration-300 opacity-0';
    loadingOverlay.innerHTML = `
      <div class="bg-white dark:bg-gray-800 p-8 rounded-lg shadow-xl text-center">
        <div class="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-500 mx-auto mb-6"></div>
        <p class="text-xl font-semibold text-gray-700 dark:text-gray-300">${title}</p>
      </div>
    `;
    document.body.appendChild(loadingOverlay);
    document.body.classList.add('overflow-hidden');
    requestAnimationFrame(() => {
      loadingOverlay.classList.remove('opacity-0');
      loadingOverlay.classList.add('opacity-100');
    });
  }
}

function hideLoading() {
  if (loadingOverlay) {
    loadingOverlay.classList.remove('opacity-100');
    loadingOverlay.classList.add('opacity-0');
    setTimeout(() => {
      if (loadingOverlay) {
        loadingOverlay.remove();
        loadingOverlay = null;
      }
      if (!modal.visibleModal && !document.querySelector('[role="dialog"]:not(.hidden)')) {
        document.body.classList.remove('overflow-hidden');
      }
    }, 300);
  }
}

function Confirm(
  title = '',
  mensaje = '',
  iconType = 'warning',
  showBtnCancel = true,
  input = false,
  inputPlaceholder = ''
) {
  return new Promise((resolve) => {
    const confirmModalId = 'tailwind-confirm-modal';
    let confirmModal = document.getElementById(confirmModalId);

    const btnCancelText = lang() ? "Cancelar" : "Cancel";
    const btnConfirmText = lang() ? "Confirmar" : "Confirm";
    const titleText = title || (lang() ? "¿Estás seguro?" : "Are you sure?");

    const iconStyles = {
      warning: { class: 'text-yellow-500 dark:text-yellow-400', icon: 'warning' },
      success: { class: 'text-green-500 dark:text-green-400', icon: 'check_circle' },
      error: { class: 'text-red-500 dark:text-red-400', icon: 'error' },
      info: { class: 'text-blue-500 dark:text-blue-400', icon: 'info' }
    };
    const currentIcon = iconStyles[iconType] || iconStyles.warning;

    let inputFieldHTML = '';
    if (input) {
      const inputTypeAttr = (typeof input === 'string' && input === 'password') ? 'password' : 'text';
      const placeholderText = inputPlaceholder || (lang() ? 'Ingrese valor aquí...' : 'Enter value here...');
      inputFieldHTML = `
        <div class="mt-4">
          <label for="confirm-input" class="sr-only">${placeholderText}</label>
          <input type="${inputTypeAttr}" id="confirm-input" placeholder="${placeholderText}" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500">
        </div>`;
    }

    if (!confirmModal) {
      confirmModal = document.createElement('div');
      confirmModal.id = confirmModalId;
      confirmModal.className = 'fixed inset-0 z-[100] flex items-center justify-center p-4';
      confirmModal.setAttribute('role', 'dialog');
      confirmModal.setAttribute('aria-modal', 'true');
      confirmModal.setAttribute('aria-labelledby', 'confirm-modal-title');
      document.body.appendChild(confirmModal);
    }

    confirmModal.innerHTML = `
      <div class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity dark:bg-gray-900 dark:bg-opacity-80 confirm-backdrop"></div>
      <div class="relative mx-auto w-full max-w-sm sm:max-w-md transform overflow-hidden rounded-xl bg-white dark:bg-gray-800 text-left shadow-2xl transition-all my-auto p-6">
        <div class="text-center">
          <span class="material-icons text-5xl ${currentIcon.class} mx-auto">${currentIcon.icon}</span>
          <h3 class="mt-3 text-2xl font-semibold leading-6 text-gray-900 dark:text-gray-100" id="confirm-modal-title">${titleText}</h3>
          <div class="mt-2">
            <p class="text-md text-gray-600 dark:text-gray-300">${mensaje}</p>
          </div>
          ${inputFieldHTML}
        </div>
        <div class="mt-6 sm:mt-8 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
          <button type="button" class="inline-flex w-full justify-center rounded-md bg-blue-600 px-4 py-2.5 text-base font-semibold text-white shadow-sm hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 sm:col-start-2 confirm-ok-button">
            ${btnConfirmText}
          </button>
          ${showBtnCancel ? `
          <button type="button" class="mt-3 inline-flex w-full justify-center rounded-md bg-white dark:bg-gray-700 px-4 py-2.5 text-base font-semibold text-gray-900 dark:text-gray-200 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 sm:col-start-1 sm:mt-0 confirm-cancel-button">
            ${btnCancelText}
          </button>` : '<div class="sm:col-start-1"></div>'}
        </div>
      </div>
    `;

    const backdrop = confirmModal.querySelector('.confirm-backdrop');
    const okButton = confirmModal.querySelector('.confirm-ok-button');
    const cancelButton = confirmModal.querySelector('.confirm-cancel-button');

    const closeAndResolve = (value) => {
      CerrarModal(confirmModalId);
      resolve(value);
    };

    okButton.addEventListener('click', () => {
      const inputValue = input ? document.getElementById('confirm-input').value : true;
      closeAndResolve(inputValue);
    });

    if (showBtnCancel && cancelButton) {
      cancelButton.addEventListener('click', () => closeAndResolve(false));
    }
    backdrop.addEventListener('click', () => closeAndResolve(false));

    AbrirModal(confirmModalId);
  });
}

window.success = alertSuccess;
window.error = alertError;
window.warning = alertWarning;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.Confirm = Confirm;
window.toggleTheme = toggleTheme;

class ResponsiveDataTable {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.error(`No se encontró el contenedor con ID: ${containerId}`);
      return;
    }

    this.defaults = {
      data: [],
      columns: [],
      rowsPerPage: 5,
      search: true,
      pagination: true,
      responsive: true,
      headerTitles: {},
      summaryFields: ['id'],
      edit: false,
      delete: false,
      tailwindClasses: {
        container: "bg-white dark:bg-gray-800 rounded-lg shadow-md p-4",
        table: "w-full border-collapse",
        tr: "border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700",
        td: "px-4 py-3 text-sm text-gray-700 dark:text-gray-300",
        mobileItem: "bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 mb-3 border border-gray-200 dark:border-gray-700",
        mobileSummary: "font-medium text-gray-800 dark:text-gray-200",
        mobileDetailRow: "flex justify-between",
        mobileLabel: "text-gray-500 dark:text-gray-400",
        mobileValue: "text-gray-700 dark:text-gray-300",
        accordionToggle: "cursor-pointer text-gray-500 hover:text-gray-700 dark:hover:text-gray-300",
        accordionContent: "text-xs text-gray-600 dark:text-gray-400",
        editButton: "text-green-600 hover:text-green-800 dark:hover:text-green-400",
        deleteButton: "text-red-500 hover:text-red-700 dark:hover:text-red-400",
        paginationButton: "mx-1 px-3 py-1 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600",
        paginationButtonActive: "bg-blue-500 text-blue-500 dark:text-blue-400 hover:bg-blue-600 dark:hover:bg-blue-400 border-blue-500"
      }
    };

    this.options = { ...this.defaults, ...options };
    this.options.tailwindClasses = {
      ...this.defaults.tailwindClasses,
      ...(options.tailwindClasses || {})
    };

    this.currentPage = 1;
    this.filteredData = [...this.options.data];

    this.init();
  }

  init() {
    this.renderContainer();
    this.renderTable();
    if (this.options.search) this.setupSearch();
    if (this.options.pagination) this.renderPagination();
  }

  renderContainer() {
    const tc = this.options.tailwindClasses;
    this.container.innerHTML = `
      <div class="${tc.container} datatable-container-wrapper">
        ${this.options.search ? `
          <div class="relative mb-4">
            <span class="material-icons absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-gray-500">search</span>
            <input type="search" class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 datatable-search-input" placeholder="${lang() ? 'Buscar...' : 'Search...'}">
          </div>` : ''}

        <div class="datatable-responsive-wrapper">
          <table class="${tc.table} hidden datatable-table"></table>
          <div class="datatable-mobile"></div>
        </div>

        ${this.options.pagination ? `<div class="flex justify-center items-center datatable-pagination mt-4"></div>` : ''}
      </div>`;
  }

  renderTable() {
    this.renderMobileView();
  }

  renderTableHeaders() {
    const headerRow = this.container.querySelector('.datatable-header');
    if (headerRow) {
      headerRow.innerHTML = '';
    }
  }

  renderTableBody() {
    const tc = this.options.tailwindClasses;
    const tbody = this.container.querySelector('.datatable-body');
    if (tbody) {
      tbody.innerHTML = '';
    }
  }

  renderMobileView() {
    const tc = this.options.tailwindClasses;
    const mobileView = this.container.querySelector('.datatable-mobile');
    if (!mobileView) return;
    mobileView.innerHTML = '';

    const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
    const endIndex = startIndex + this.options.rowsPerPage;
    const paginatedData = this.filteredData.slice(startIndex, endIndex);

    const formatMobileContent = (value, columnKey) => {
      if (value === null || typeof value === 'undefined' || value === '') return '<span class="text-gray-400 dark:text-gray-500">-</span>';
      if (typeof value !== 'string') value = String(value);
      const isHtmlTag = /<[a-z][\s\S]*>/i.test(value);

      if (value.length > 25 && !isHtmlTag) {
        const shortText = value.substring(0, 25) + '...';
        const randomId = `mobile-accordion-${columnKey}-${Math.random().toString(36).substr(2, 9)}`;
        return `
              <div class="relative">
                <span>${shortText}</span>
                <button class="${tc.accordionToggle} accordion-toggle-btn" data-target="${randomId}">
                    <span class="material-icons text-sm">expand_more</span>
                </button>
                <div id="${randomId}" class="${tc.accordionContent} hidden mt-1 p-2 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-gray-700 text-xs">
                  ${value}
                </div>
              </div>`;
      }
      return value;
    };

    paginatedData.forEach(item => {
      const itemElement = document.createElement('div');
      itemElement.className = tc.mobileItem;

      const summaryText = this.options.summaryFields
        .map(fieldKey => {
          const column = this.options.columns.find(c => c.key === fieldKey);
          const title = this.options.headerTitles[fieldKey] || (column ? column.title : fieldKey);
          return `<span class="font-semibold">${title} </span> ${item[fieldKey] || '-'}`;
        }).join(' <span class="text-gray-300 dark:text-gray-600 mx-1">|</span> ');

      itemElement.innerHTML = `<div class="${tc.mobileSummary} text-sm">${summaryText}</div>`;

      const detailsContainer = document.createElement('div');
      detailsContainer.className = "mt-2 space-y-1";
      this.options.columns.forEach(column => {
        if (this.options.summaryFields.includes(column.key)) return;

        const detailRow = document.createElement('div');
        detailRow.className = tc.mobileDetailRow;
        const label = this.options.headerTitles[column.key] || column.title || column.key;
        let cellValue = isDate(item[column.key]) ? parseDate(item[column.key]) : item[column.key];

        detailRow.innerHTML = `
          <span class="${tc.mobileLabel} text-xs">${label}:</span>
          <span class="${tc.mobileValue} text-xs text-right">${formatMobileContent(cellValue, column.key)}</span>`;
        detailsContainer.appendChild(detailRow);
      });
      itemElement.appendChild(detailsContainer);

      if (this.options.edit || this.options.delete) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'mt-3 pt-3 border-t border-gray-200 dark:border-gray-600 flex justify-end space-x-2';
        if (this.options.edit) {
          const editBtn = document.createElement('button');
          editBtn.className = `${tc.editButton} flex items-center text-xs py-1 px-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600`;
          editBtn.innerHTML = `<span class="material-icons text-base mr-1 text-green-600">edit</span> ${lang() ? "Editar" : "Edit"}`;
          editBtn.onclick = (e) => {
            const editCallback = typeof this.options.edit === 'function' ? this.options.edit : window[this.options.edit];
            if (typeof editCallback === 'function') editCallback(e, item.id || item);
          };
          actionsDiv.appendChild(editBtn);
        }
        if (this.options.delete) {
          const deleteBtn = document.createElement('button');
          deleteBtn.className = `${tc.deleteButton} flex items-center text-xs py-1 px-2 rounded hover:bg-gray-100 dark:hover:bg-gray-600`;
          deleteBtn.innerHTML = `<span class="material-icons text-base mr-1 text-red-500">delete</span> ${lang() ? "Eliminar" : "Delete"}`;
          deleteBtn.onclick = (e) => {
            const deleteCallback = typeof this.options.delete === 'function' ? this.options.delete : window[this.options.delete];
            if (typeof deleteCallback === 'function') deleteCallback(e, item.id || item);
          };
          actionsDiv.appendChild(deleteBtn);
        }
        itemElement.appendChild(actionsDiv);
      }
      mobileView.appendChild(itemElement);
    });
    this.setupMobileAccordionListeners(mobileView);
  }

  setupMobileAccordionListeners(contextElement) {
    const tc = this.options.tailwindClasses;
    contextElement.querySelectorAll('.accordion-toggle-btn').forEach(toggle => {
      const newToggle = toggle.cloneNode(true);
      toggle.parentNode.replaceChild(newToggle, toggle);

      newToggle.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const targetId = newToggle.getAttribute('data-target');
        const content = document.getElementById(targetId);
        const icon = newToggle.querySelector('.material-icons');
        if (content) {
          content.classList.toggle('hidden');
          if (icon) icon.textContent = content.classList.contains('hidden') ? 'expand_more' : 'expand_less';
        }
      });
    });
  }

  renderPagination() {
    const tc = this.options.tailwindClasses;
    const paginationContainer = this.container.querySelector('.datatable-pagination');
    if (!paginationContainer) return;

    paginationContainer.innerHTML = '';
    const pageCount = Math.ceil(this.filteredData.length / this.options.rowsPerPage);

    if (pageCount <= 1) return;

    const createButton = (content, pageNum, isActive = false, isDisabled = false, isIcon = false) => {
      const button = document.createElement('button');
      button.innerHTML = content;
      button.className = `${tc.paginationButton} ${isActive ? tc.paginationButtonActive : ''} ${isIcon ? 'px-2' : 'px-3'}`;
      if (isDisabled) {
        button.disabled = true;
        button.classList.add('opacity-50', 'cursor-not-allowed');
      } else {
        button.onclick = () => {
          this.currentPage = pageNum;
          this.updateTable();
        };
      }
      return button;
    };

    paginationContainer.appendChild(createButton(
      '<span class="material-icons text-lg">chevron_left</span>',
      this.currentPage - 1,
      false,
      this.currentPage === 1,
      true
    ));

    let startPage = Math.max(1, this.currentPage - 2);
    let endPage = Math.min(pageCount, this.currentPage + 2);

    if (this.currentPage <= 3) {
      endPage = Math.min(pageCount, 5);
    }
    if (this.currentPage >= pageCount - 2) {
      startPage = Math.max(1, pageCount - 4);
    }

    if (startPage > 1) {
      paginationContainer.appendChild(createButton('1', 1));
      if (startPage > 2) {
        const ellipsis = document.createElement('span');
        ellipsis.className = "px-3 py-2 text-sm text-gray-500 dark:text-gray-400";
        ellipsis.textContent = "...";
        paginationContainer.appendChild(ellipsis);
      }
    }

    for (let i = startPage; i <= endPage; i++) {
      paginationContainer.appendChild(createButton(String(i), i, i === this.currentPage));
    }

    if (endPage < pageCount) {
      if (endPage < pageCount - 1) {
        const ellipsis = document.createElement('span');
        ellipsis.className = "px-3 py-2 text-sm text-gray-500 dark:text-gray-400";
        ellipsis.textContent = "...";
        paginationContainer.appendChild(ellipsis);
      }
      paginationContainer.appendChild(createButton(String(pageCount), pageCount));
    }

    paginationContainer.appendChild(createButton(
      '<span class="material-icons text-lg">chevron_right</span>',
      this.currentPage + 1,
      false,
      this.currentPage === pageCount,
      true
    ));
  }

  setupSearch() {
    const searchInput = this.container.querySelector('.datatable-search-input');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
      const searchTerm = e.target.value.toLowerCase().trim();
      this.filteredData = this.options.data.filter(item => {
        return this.options.columns.some(column => {
          const value = item[column.key];
          return String(value).toLowerCase().includes(searchTerm);
        });
      });
      this.currentPage = 1;
      this.updateTable();
    });
  }

  updateTable() {
    this.renderTableHeaders();
    this.renderTableBody();
    if (this.options.responsive) {
      this.renderMobileView();
    }
    if (this.options.pagination) {
      this.renderPagination();
    }
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

  updateOptions(newOptions) {
    this.options = { ...this.options, ...newOptions };
    this.updateTable();
  }
}

function isDate(value) {

  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (!regex.test(value)) return false;

  const [anio, mes, dia] = value.split("-").map(Number);

  const fecha = new Date(anio, mes - 1, dia);

  return fecha.getFullYear() === anio &&
    fecha.getMonth() + 1 === mes &&
    fecha.getDate() === dia;

}

function parseDate(value) {
  let val = value;
  if (isDate(value) && lang()) {

    const [anio, mes, dia] = value.split("-").map(Number);
    const fecha = new Date(anio, mes - 1, dia);
    const diaFormateado = String(fecha.getDate()).padStart(2, "0");
    const mesFormateado = String(fecha.getMonth() + 1).padStart(2, "0");
    const anioFormateado = fecha.getFullYear();

    const formato = `${diaFormateado}/${mesFormateado}/${anioFormateado}`;
    value = formato;
  }
  else if (isDate(value)) {
    const [anio, mes, dia] = value.split("-").map(Number);
    const fecha = new Date(anio, mes - 1, dia);

    const diaFormateado = String(fecha.getDate()).padStart(2, "0");
    const mesFormateado = String(fecha.getMonth() + 1).padStart(2, "0");
    const anioFormateado = fecha.getFullYear();

    const formato = `${anioFormateado}/${mesFormateado}/${diaFormateado}`;
    value = formato;
  }
  return val;
}