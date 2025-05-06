
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
