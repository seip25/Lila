document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("#btn_menu").addEventListener("click", (event) => openMenu({ event: event }));
    document.querySelector("#btn_close_menu").addEventListener("click", (event) => closeMenu({ event: event }));
  });