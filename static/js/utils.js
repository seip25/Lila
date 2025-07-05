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

// Make functions globally available
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