/**
 * Lila-SPA Navigation Engine
 * Provides Single Page Application behavior with SWR caching.
 */
(function () {
  const CONTENT_ID = 'lila-spa-content';
  const TIMEOUT_MS = 5000;

  const pageCache = new Map();
  const langsHistory = {};

  /**
   * Logs debug messages to the console if debugging is enabled.
   * 
   * @param {...*} args - The arguments to log
   * @returns {void}
   */
  function logDebug(...args) {
    if (window.LILA_DEBUG) {
      console.log('[Lila SPA]', ...args);
    }
  }

  const initialLang = document.documentElement.lang || 'en';
  if (window.LILA_TRANSLATIONS) {
    langsHistory[initialLang] = window.LILA_TRANSLATIONS;
    logDebug('Initial translations loaded for language:', initialLang);
  }

  /**
   * Normalizes a URL for caching and routing keys.
   * 
   * @param {string} url - The URL to normalize
   * @returns {string}
   */
  function getCacheKey(url) {
    try {
      const urlObj = new URL(url, window.location.origin);
      urlObj.searchParams.delete('source');
      urlObj.searchParams.delete('set-lang');
      return urlObj.pathname + urlObj.search + urlObj.hash;
    } catch (e) {
      return url;
    }
  }

  /**
   * Instantly translates all text nodes in the DOM on the client side.
   * 
   * @param {string} targetLang - The target language code
   * @returns {void}
   */
  function translatePageInstant(targetLang) {
    const currentLang = document.documentElement.lang || 'en';
    const currentDict = langsHistory[currentLang];
    const targetDict = langsHistory[targetLang];
    
    if (!currentDict || !targetDict) {
      logDebug('Missing dictionaries for translation from', currentLang, 'to', targetLang);
      return;
    }

    logDebug('Translating page instantly from', currentLang, 'to', targetLang);

    const walker = document.createTreeWalker(
      document.getElementById(CONTENT_ID) || document.body,
      NodeFilter.SHOW_TEXT,
      null,
      false
    );

    let node;
    while ((node = walker.nextNode())) {
      const text = node.nodeValue.trim();
      if (!text) {
        continue;
      }

      let originalKey = null;
      for (const [key, val] of Object.entries(currentDict)) {
        if (val === text || key === text) {
          originalKey = key;
          break;
        }
      }

      if (originalKey && targetDict[originalKey]) {
        const leftSpace = node.nodeValue.match(/^\s*/)[0];
        const rightSpace = node.nodeValue.match(/\s*$/)[0];
        node.nodeValue = leftSpace + targetDict[originalKey] + rightSpace;
      }
    }

    document.documentElement.lang = targetLang;
  }

  /**
   * Renders the fetched page content to the DOM.
   * 
   * @param {Object} data - The page response JSON data
   * @param {string} url - The target URL
   * @param {boolean} push - Whether to push to history
   * @param {string} [responseUrl] - The final resolved URL
   * @returns {void}
   */
  function renderPage(data, url, push, responseUrl) {
    logDebug('Rendering page:', url, 'Push state:', push);

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
        const newScript = document.createElement('script');
        Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
        newScript.textContent = oldScript.textContent;
        
        if (oldScript.src) {
           const existing = document.head.querySelector(`script[src="${oldScript.src}"]`);
           if (existing && (oldScript.hasAttribute('data-spa-reload') || oldScript.src.includes('source=frontend'))) {
              existing.remove();
           }
           if (!document.head.querySelector(`script[src="${oldScript.src}"]`)) {
              document.head.appendChild(newScript);
           }
        } else {
          const content = oldScript.textContent.trim();
          if (content) {
            Array.from(document.head.querySelectorAll('script:not([src])'))
              .filter(s => s.textContent.trim() === content)
              .forEach(s => s.remove());
            document.head.appendChild(newScript);
          }
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
      let finalUrl = responseUrl || url;
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
    document.dispatchEvent(new CustomEvent('lila:content-loaded', {
      detail: { url, data }
    }));
  }

  /**
   * Revalidates page data from the server.
   * 
   * @param {string} url - The target URL
   * @param {boolean} push - Whether to push to history on render
   * @param {boolean} [forceRender=false] - Whether to force DOM updates
   * @returns {Promise<void>}
   */
  async function revalidate(url, push, forceRender = false) {
    logDebug('Revalidating URL from server:', url);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const requestUrl = url;
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
        logDebug('Unauthorized/Forbidden response, redirecting window:', url);
        window.location.href = url;
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const cacheKey = getCacheKey(url);

      const cached = pageCache.get(cacheKey);
      const contentChanged = !cached || cached.body !== data.body || JSON.stringify(cached.meta) !== JSON.stringify(data.meta);

      logDebug('Revalidation completed. Content changed:', contentChanged);

      pageCache.set(cacheKey, data);
      
      const currentLang = data.lang || 'en';
      if (data.translations) {
        langsHistory[currentLang] = data.translations;
      }

      if (forceRender || contentChanged) {
        renderPage(data, url, push, response.url);
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('SPA Navigation failed:', error);
      }
      if (forceRender) {
        window.location.href = url;
      }
    }
  }

  /**
   * Navigates to a new page using SPA SWR cache revalidation.
   * 
   * @param {string} url - The target URL
   * @param {boolean} [push=true] - Whether to push history
   * @returns {Promise<void>}
   */
  async function navigate(url, push = true) {
    logDebug('Navigating to:', url);
    try {
      const urlObj = new URL(url, window.location.origin);
      const targetLang = urlObj.searchParams.get('lang');
      if (targetLang && targetLang !== document.documentElement.lang) {
        translatePageInstant(targetLang);
      }
    } catch (e) {
    }

    const cacheKey = getCacheKey(url);
    const cachedData = pageCache.get(cacheKey);

    if (cachedData) {
      logDebug('Cache hit for URL:', url);
      renderPage(cachedData, url, push);
      revalidate(url, false);
      return;
    }

    logDebug('Cache miss for URL, initiating server load:', url);
    await revalidate(url, push, true);
  }

  window.lilaNav = { navigate };

  /**
   * Registers event listeners for clicks, hovers, and touches.
   * 
   * @returns {void}
   */
  function initSPA() {
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
        logDebug('SPA link clicked:', link.href);
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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSPA);
  } else {
    initSPA();
  }
})();
