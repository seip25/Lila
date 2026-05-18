document.addEventListener("DOMContentLoaded", () => {
  const spaEnabled = true;
  if (!spaEnabled) return;
  const mainContent = document.querySelector("main");
  if (!mainContent) return;
  
  function updateLinks() {
    document.querySelectorAll("a").forEach((link) => {
      if (link.dataset.spaInitialized) return;
      link.dataset.spaInitialized = "true";
      const href = link.getAttribute("href");
      if (!href) return;
      if (href.startsWith("http") && !href.startsWith(window.location.origin)) return;
      if (href.startsWith("#") || href.startsWith("javascript:")) return;
      if (link.hasAttribute("download") || link.getAttribute("target") === "_blank" || link.hasAttribute("data-no-spa")) return;
      
      link.addEventListener("click", (e) => {
        e.preventDefault();
        navigateTo(href);
      });
    });
  }

  async function navigateTo(url) {
    try {
      const urlObj = new URL(url, window.location.origin);
      urlObj.searchParams.set("source", "frontend");
      const cleanUrl = urlObj.toString();
      
      document.dispatchEvent(new CustomEvent("lila:navigation", { detail: { url: url } }));
      
      const response = await fetch(cleanUrl, {
        headers: { "X-Lila-SPA": "true" }
      });
      
      if (!response.ok) {
        window.location.href = url;
        return;
      }
      
      const data = await response.json();
      if (data.redirect) {
        navigateTo(data.redirect);
        return;
      }
      
      if (data.html) {
        mainContent.innerHTML = data.html;
      }
      
      if (data.title) {
        document.title = data.title;
      }
      
      window.history.pushState({}, data.title || "", url);
      
      if (data.meta) {
        Object.entries(data.meta).forEach(([name, content]) => {
          let meta = document.querySelector(`meta[name="${name}"]`);
          if (!meta) {
            meta = document.createElement("meta");
            meta.setAttribute("name", name);
            document.head.appendChild(meta);
          }
          meta.setAttribute("content", content);
        });
      }
      
      updateLinks();
      
      const scripts = mainContent.querySelectorAll("script");
      scripts.forEach((script) => {
        const newScript = document.createElement("script");
        Array.from(script.attributes).forEach((attr) => {
          newScript.setAttribute(attr.name, attr.value);
        });
        newScript.appendChild(document.createTextNode(script.innerHTML));
        script.parentNode.replaceChild(newScript, script);
      });
      
      document.dispatchEvent(new CustomEvent("lila:content-loaded", { detail: { url: url } }));
    } catch (err) {
      console.error("SPA Navigation failed:", err);
      window.location.href = url;
    }
  }

  window.addEventListener("popstate", () => {
    navigateTo(window.location.pathname + window.location.search);
  });

  updateLinks();

  const observer = new MutationObserver(() => {
    updateLinks();
  });
  observer.observe(document.body, { childList: true, subtree: true });
});
