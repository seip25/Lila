document.addEventListener("click", function (e) {
  const btn = e.target.closest("button, a[role='button']");
  if (!btn || btn.classList.contains("fab")) return;

  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  const x = e.clientX - rect.left - size / 2;
  const y = e.clientY - rect.top - size / 2;

  const ripple = document.createElement("span");
  ripple.className = "ripple";
  ripple.style.width = ripple.style.height = size + "px";
  ripple.style.left = x + "px";
  ripple.style.top = y + "px";

  btn.appendChild(ripple);
  ripple.addEventListener("animationend", () => ripple.remove());
});

(function () {
  function initDrawer() {
    const mainEl = document.querySelector("main");
    const aside = mainEl ? mainEl.querySelector(":scope > aside") : null;
    if (!aside || document.querySelector(".lila-drawer")) return;

    const overlay = document.createElement("div");
    overlay.className = "lila-drawer-overlay";
    document.body.appendChild(overlay);

    const drawer = document.createElement("div");
    drawer.className = "lila-drawer";
    drawer.innerHTML = aside.innerHTML;
    document.body.appendChild(drawer);

    const toggle = document.createElement("button");
    toggle.className = "lila-drawer-toggle";
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
      overlay.classList.add("open");
      document.body.style.overflow = "hidden";
    }

    function closeDrawer() {
      drawer.classList.remove("open");
      overlay.classList.remove("open");
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
})();

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

  snackbar.className = "show";

  if (options.type) {
    snackbar.classList.add(options.type);
  } else {
    snackbar.classList.add("info");
  }

  snackbar.textContent = options.message || "";
  setTimeout(() => {
    snackbar.classList.add("show");
  }, 10);

  const duration = options.duration || 3000;
  if (snackbar.timeoutId) {
    clearTimeout(snackbar.timeoutId);
  }

  snackbar.timeoutId = setTimeout(function () {
    snackbar.className = "";
  }, duration);
}
