/**
 * Lila-SPA Navigation Engine
 * Provides Single Page Application behavior for Twig and React.
 */
(function () {
  const CONTENT_ID = 'lila-spa-content';
  const TIMEOUT_MS = 5000;

  /**
   * Navigates to a new page using SPA logic.
   * 
   * @param {string} url - The target URL
   * @param {boolean} [push=true] - Whether to push to browser history
   * @returns {Promise<void>}
   */
  async function navigate(url, push = true) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      let requestUrl = url;

      const separator = requestUrl.includes('?') ? '&' : '?';
      const response = await fetch(`${requestUrl}${separator}source=frontend`, {
        signal: controller.signal,
        headers: {
          'X-Lila-SPA': 'true',
          'Accept': 'application/json'
        }
      });

      clearTimeout(timeoutId);

      if (response.status === 401 || response.status === 403) {
        window.location.href = url;
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.meta) {
        document.title = data.meta.title || document.title;
        ['description', 'keywords', 'author'].forEach(name => {
          const el = document.querySelector(`meta[name="${name}"]`);
          if (el && data.meta[name]) el.setAttribute("content", data.meta[name]);
        });
      }

      if (data.css && Array.isArray(data.css)) {
        data.css.forEach(href => {
          if (!document.head.querySelector(`link[href="${href}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            document.head.appendChild(link);
          }
        });
      }

      if (data.scripts && Array.isArray(data.scripts)) {
        data.scripts.forEach(scriptData => {
          const src = typeof scriptData === 'string' ? scriptData : scriptData.src;
          if (src) {
            if (!document.head.querySelector(`script[src="${src}"]`)) {
              const script = document.createElement('script');
              script.src = src;
              script.type = scriptData.type || 'module';
              document.head.appendChild(script);
            }
          } else if (scriptData.content) { 
            Array.from(document.head.querySelectorAll('script:not([src])'))
              .filter(s => s.textContent.trim() === scriptData.content.trim())
              .forEach(s => s.remove());

            const script = document.createElement('script');
            script.textContent = scriptData.content;
            script.type = scriptData.type || 'module';
            document.head.appendChild(script);
          }
        });
      }

      const container = document.getElementById(CONTENT_ID);
      if (container) {
        container.innerHTML = data.body;

        const partialScripts = container.querySelectorAll('script');
        const partialLinks = container.querySelectorAll('link[rel="stylesheet"]');

        partialLinks.forEach(link => {
          if (!document.head.querySelector(`link[href="${link.href}"]`)) {
            document.head.appendChild(link.cloneNode(true));
          }
          link.remove();
        });

        partialScripts.forEach(oldScript => {
          const src = oldScript.src;
          if (src) {
            if (!document.head.querySelector(`script[src="${src}"]`)) {
              const newScript = document.createElement('script');
              Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
              document.head.appendChild(newScript);
            }
          } else { 
            Array.from(document.head.querySelectorAll('script:not([src])'))
              .filter(s => s.textContent.trim() === oldScript.textContent.trim())
              .forEach(s => s.remove());

            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            newScript.textContent = oldScript.textContent;
            document.head.appendChild(newScript);
          }
          oldScript.remove();
        });

        if (!url.includes('set-lang=true')) {
          const hash = url.split('#')[1];
          if (hash) {
            const element = document.getElementById(hash);
            if (element) {
              element.scrollIntoView({ behavior: 'smooth' });
            }
          } else {
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }
      }

      if (push) {
        let finalUrl = response.url || url;
        try {
          const urlObj = new URL(finalUrl);
          const hasSetLang = urlObj.searchParams.has('set-lang');
          urlObj.searchParams.delete('source');
          urlObj.searchParams.delete('set-lang');
          if (hasSetLang) {
            urlObj.searchParams.delete('lang');
          }
          finalUrl = urlObj.pathname + urlObj.search + urlObj.hash;
        } catch (e) {
          finalUrl = finalUrl.replace(/[?&]source=frontend/, '').replace(/[?&]set-lang=true/, '');
        }
        window.history.pushState({ url: finalUrl }, data.meta?.title || '', finalUrl);
      }

      document.dispatchEvent(new CustomEvent('lila:navigation', {
        detail: { url, data }
      }));

    } catch (error) {
      if (error.name === 'AbortError') {
        console.warn('SPA Navigation timeout, redirecting...');
      } else {
        console.error('SPA Navigation failed:', error);
      }
      window.location.href = url;
    }
  }

  window.lilaNav = { navigate };

  document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');

      if (link &&
        link.href &&
        link.href.startsWith(window.location.origin) &&
        !link.hasAttribute('download') &&
        !link.hasAttribute('data-no-spa') &&
        link.target !== '_blank' &&
        !e.ctrlKey && !e.metaKey && !e.shiftKey) {

        e.preventDefault();
        navigate(link.href);
      }
    });

    window.addEventListener('popstate', (e) => {
      if (e.state && e.state.url) {
        navigate(e.state.url, false);
      } else {
        window.location.reload();
      }
    });
  });
})();
