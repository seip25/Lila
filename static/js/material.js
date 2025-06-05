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

function lang() {
  return document.querySelector('html').lang == "es";
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

  openModal: function (modal) {
    document.documentElement.classList.add(this.isOpenClass, this.openingClass);

    modal.showModal();
    this.visibleModal = modal;

    setTimeout(() => {
      document.documentElement.classList.remove(this.openingClass);
    }, this.animationDuration);
  },

  closeModal: function (modal) {
    document.documentElement.classList.add(this.closingClass);

    setTimeout(() => {
      document.documentElement.classList.remove(this.closingClass, this.isOpenClass);
      modal.close();
      this.visibleModal = null;
    }, this.animationDuration);
  },
  modalAlert: function (mensaje, tipo = 'info', tiempoCierre = 3000) {

    let alertModal = document.getElementById('alert-material');

    const acept = lang() ? "Aceptar" : "Accept";

    if (!alertModal) {
      alertModal = document.createElement('dialog');
      alertModal.id = 'alert-material';
      alertModal.innerHTML = `
          <article class="alert-content container ">
          <div class="flex column">
          <div class="flex center gap-2">
           <div class="alert-icon"></div>
            <h3 class="alert-title"></h3>
          </div>
            <p class="alert-message flex center"></p>
          </div>
            <footer class="flex center">
              <button class="btn-secondary " onclick="CerrarModal('alert-material')">${acept}</button>
            </footer>
          </article>
        `;
      document.body.appendChild(alertModal);
    }

    const article = alertModal.querySelector('article');
    const icon = alertModal.querySelector('.alert-icon');
    const title = alertModal.querySelector('.alert-title');
    const message = alertModal.querySelector('.alert-message');

    article.className = 'alert-content';
    article.classList.add(tipo);

    title.textContent = tipo == "success" ? lang() ? "Éxito" : "Success" : tipo == "error" ? lang() ? "Error" : "Error" : lang() ? "Información" : "Information";
    message.textContent = mensaje;

    switch (tipo) {
      case 'success':
        icon.innerHTML = '✅';
        break;
      case 'error':
        icon.innerHTML = '❌';
        break;
      case 'warning':
        icon.innerHTML = '⚠️';
        break;
      default:
        icon.innerHTML = 'ℹ️';
    }

    this.openModal(alertModal);

    if (tiempoCierre > 0) {
      setTimeout(() => {
        this.closeModal(alertModal);
      }, tiempoCierre);
    }
  }

};

document.addEventListener('DOMContentLoaded', () => {
  modal.init();
});

function AbrirModal(modalId) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) modal.openModal(modalElement);
}

function CerrarModal(modalId) {
  const modalElement = document.getElementById(modalId);
  if (modalElement) modal.closeModal(modalElement);
}

function ShowModal(modalId) {
AbrirModal(modalId);
}
function CloseModal(modalId) {
CerrarModal(modalId);
}
 
function success(mensaje = false, titulo = 'Ok') {
  modal.modalAlert(mensaje || (lang() ? "Operación exitosa" : "Operation successful"), 'success', 3000);
}
 
function error(mensaje = '', titulo = 'Error', showConfirmButton = true) {
  modal.modalAlert(mensaje || (lang() ? "Ha ocurrido un error" : "An error occurred"), 'error', showConfirmButton ? 0 : 3000);
}
 
function warning(mensaje = false, titulo = '') {
  modal.modalAlert(mensaje || (lang() ? "Advertencia" : "Warning"), 'warning', 3000);
}
 
let loadingModal;
function showLoading(title = lang() ? "Cargando..." : "Loading...") {
  if (!loadingModal) {
    loadingModal = document.createElement('div');
    loadingModal.id = 'loading-modal';
    loadingModal.className = 'modal-loading';
    loadingModal.innerHTML = `
      <div class="loading-content">
        <span aria-busy="true">${title}</span>
      </div>
    `;
    document.body.appendChild(loadingModal);
    document.documentElement.classList.add('modal-open');
  }
}

function hideLoading() {
  if (loadingModal) {
    document.documentElement.classList.remove('modal-open');
    loadingModal.remove();
    loadingModal = null;
  }
}
 
function Confirm(
  title = '',
  mensaje = '',
  icon = 'warning',
  ShowBtnCancel = true,
  input = false,
  inputPlaceholder = ''
) {
  return new Promise((resolve) => {
    const confirmModal = document.createElement('dialog');
    confirmModal.id = 'confirm-modal';
    
    const btnCancel = lang() ? "Cancelar" : "Cancel";
    const btnConfirm = lang() ? "Confirmar" : "Confirm";
    
    if (!title) {
      title = lang() ? "¿Estás seguro?" : "Are you sure?";
    }
    
    let inputField = '';
    if (input) {
      inputField = `
        <label>
          ${inputPlaceholder}
          <input type="${input === 'password' ? 'password' : 'text'}" id="confirm-input" placeholder="${inputPlaceholder}">
        </label>
      `;
    }
    
    confirmModal.innerHTML = `
      <article class="container">
        <header>
          <h3>${title}</h3>
        </header>
        <p>${mensaje}</p>
        ${inputField}
        <footer class="grid">
         
          <button class="btn-error" id="confirm-ok">${btnConfirm}</button>

           ${ShowBtnCancel ? 
            `<button class="mt-2 btn-secondary" id="confirm-cancel">${btnCancel}</button>` 
            : ''}
        </footer>
      </article>
    `;
    
    document.body.appendChild(confirmModal);
    modal.openModal(confirmModal);
    
    // Agregar event listeners correctamente
    const handleConfirm = () => {
      const inputValue = input ? document.getElementById('confirm-input').value : true;
      modal.closeModal(confirmModal);
      setTimeout(() => confirmModal.remove(), modal.animationDuration);
      resolve(inputValue);
    };
    
    const handleCancel = () => {
      modal.closeModal(confirmModal);
      setTimeout(() => confirmModal.remove(), modal.animationDuration);
      resolve(false);
    };
    
    document.getElementById('confirm-ok').addEventListener('click', handleConfirm);
    
    if (ShowBtnCancel) {
      document.getElementById('confirm-cancel').addEventListener('click', handleCancel);
    }
     
    confirmModal.addEventListener('click', (e) => {
      if (e.target === confirmModal) {
        handleCancel();
      }
    });
  });
}
 
const style = document.createElement('style');
style.textContent = `
  .modal-loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
  }
  
  .loading-content {
    background: white;
    padding: 2rem;
    border-radius: 0.5rem;
    text-align: center;
  }
  
  .loading-content span {
    font-size: 1.2rem;
  }
  
  #confirm-modal {
    max-width: 500px;
  }
  
  #confirm-modal article {
    padding: 1.5rem;
  }
  
  #confirm-modal footer {
    margin-top: 1.5rem;
    gap: 1rem;
  }
`;
document.head.appendChild(style);
 


window.AbrirModal = AbrirModal;
window.CerrarModal = CerrarModal;
window.modalAlert = function (response) {
  const mensaje = response.msg || (response.success ?
    lang() ? "Se ejecuto la operación con éxito" : "The operation was executed successfully" :
    response.error ? lang() ? "Error en la operación" : "Error in the operation" :
      response.warning ? lang() ? "Advertencia" : "Warning" :
        lang() ? "Información" : "Information");
  const tipo = response.success ? 'success': !response.success ? 'error' : response.error ? 'error' : response.warning ? 'warning' : 'info';
  const tiempoCierre = 3000;
  modal.modalAlert(mensaje, tipo, tiempoCierre);
};

window.success = success;
window.error = error;
window.warning = warning;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.Confirm = Confirm;



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
            summaryFields: ['id', 'fecha']
        };

        this.options = { ...this.defaults, ...options };

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
        this.container.innerHTML = `
                    <div class="datatable-container">
                        ${this.options.search ? `
                        <div class="datatable-search">
                            <i class="icon icon-search"></i>
                            <input type="text" class="datatable-search-input" placeholder="">
                        </div>
                        ` : ''}
                        
                        <div class="datatable-responsive">
                            <table class="datatable-table">
                                <thead class="datatable-header"></thead>
                                <tbody class="datatable-body"></tbody>
                            </table>
                            
                            <div class="datatable-mobile"></div>
                        </div>
                        
                        ${this.options.pagination ? `
                        <div class="datatable-pagination container mx-sm"></div>
                        ` : ''}
                    </div>
                `;
    }

    renderTable() {
        this.renderTableHeaders();
        this.renderTableBody();
        if (this.options.responsive) {
            this.renderMobileView();
        }
    }

    renderTableHeaders() {
        const headerRow = this.container.querySelector('.datatable-header');
        headerRow.innerHTML = '';

        this.options.columns.forEach(column => {
            const th = document.createElement('th');
            th.textContent = this.options.headerTitles[column.key] || column.title || column.key;
            headerRow.appendChild(th);
        });
    }

    renderTableBody() {
        const tbody = this.container.querySelector('.datatable-body');
        tbody.innerHTML = '';

        const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
        const endIndex = startIndex + this.options.rowsPerPage;
        const paginatedData = this.filteredData.slice(startIndex, endIndex);

        paginatedData.forEach(item => {
            const tr = document.createElement('tr');

            this.options.columns.forEach(column => {
                const td = document.createElement('td');
                td.innerHTML = item[column.key] || '-';
                tr.appendChild(td);
            });

            tbody.appendChild(tr);
        });
    }

    renderMobileView() {
        const mobileView = this.container.querySelector('.datatable-mobile');
        mobileView.innerHTML = '';

        const startIndex = (this.currentPage - 1) * this.options.rowsPerPage;
        const endIndex = startIndex + this.options.rowsPerPage;
        const paginatedData = this.filteredData.slice(startIndex, endIndex);

        paginatedData.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'datatable-mobile-item shadow mt-2';

            const summary = document.createElement('b'); 
            summary.classList.add('text-fill')
            const summaryText = this.options.summaryFields
                .map(field => `${this.getHeaderTitle(field)}: ${item[field] || '-'}`)
                .join(' | ');
            summary.innerHTML = `
                        <span  >${summaryText}</span>
                    `;

            const details = document.createElement('div');
            details.className = 'details';

            this.options.columns.forEach(column => {
                if (this.options.summaryFields.includes(column.key)) return;

                const row = document.createElement('div');
                row.className = 'row';

                const label = document.createElement('span');
                label.className = 'label';
                label.textContent = `${this.getHeaderTitle(column.key)}:`;

                const value = document.createElement('span');
                value.className = 'value';
                value.innerHTML = item[column.key] || '-';

                row.appendChild(label);
                row.appendChild(value);
                details.appendChild(row);
            });

            itemElement.appendChild(summary);
            itemElement.appendChild(details);
            mobileView.appendChild(itemElement);
        });
    }

    getHeaderTitle(key) {
        return this.options.headerTitles[key] ||
            this.options.columns.find(c => c.key === key)?.title ||
            key;
    }

    renderPagination() {
        const paginationContainer = this.container.querySelector('.datatable-pagination');
        if (!paginationContainer) return;

        paginationContainer.innerHTML = '';
        const pageCount = Math.ceil(this.filteredData.length / this.options.rowsPerPage);

        if (pageCount > 1) {
            const prevButton = this.createPaginationButton('«', 'prev ');
            prevButton.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this.updateTable();
                }
            });
            paginationContainer.appendChild(prevButton);
        }

        for (let i = 1; i <= pageCount; i++) {
            const pageButton = this.createPaginationButton(i, i);
            if (i === this.currentPage) {
                pageButton.classList.add('active'); 
            }

            pageButton.addEventListener('click', () => {
                this.currentPage = i;
                this.updateTable();
            });

            paginationContainer.appendChild(pageButton);
        }

        if (pageCount > 1) {
            const nextButton = this.createPaginationButton('»', 'next');
            nextButton.addEventListener('click', () => {
                if (this.currentPage < pageCount) {
                    this.currentPage++;
                    this.updateTable();
                }
            });
            paginationContainer.appendChild(nextButton);
        }
    }

    createPaginationButton(text, className) {
        const button = document.createElement('button');
        button.textContent = text;
        button.className = className + ' fill dark';
        button.setAttribute('type', 'button');
        return button;
    }

    setupSearch() {
        const searchInput = this.container.querySelector('.datatable-search-input');
        if (!searchInput) return;

        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();

            if (searchTerm === '') {
                this.filteredData = [...this.options.data];
            } else {
                this.filteredData = this.options.data.filter(item => {
                    return Object.values(item).some(value =>
                        String(value).toLowerCase().includes(searchTerm)
                    );
                });
            }

            this.currentPage = 1;
            this.updateTable();
        });
    }

    updateTable() {
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
