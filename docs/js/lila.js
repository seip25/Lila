
const App = {
  routes: {},
  root: null,

  createComponent(name, options) {
    class CustomComponent extends HTMLElement {
      constructor() {
        super();
        this.props = {};
        this.state = {};
        this._children = this.innerHTML;
        this._elementCahche = new Map();
        this._bindings = new Map();
        this.exposeActions(options.actions);
      }

      exposeActions(actions) {
        if (actions) {
          Object.keys(actions).forEach(actionName => {
            this[actionName] = actions[actionName].bind(this);
          });
        }
      }
      connectedCallback() {
        this.props = this.getProps();
        if (options.state) this.state = options.state(this.props);

        this.render().then(() => {
          if (options.onMount) {
            if (typeof options.onMount === 'function') {
              options.onMount.call(this);
            }
          }
          this.setupModelBindings();
          this.cacheBoundElements();
          this.exposeActions(options.actions);


          if (options.onUpdate) options.onUpdate.call(this);
        });
      }

      disconnectedCallback() {
        if (options.onDestroy) {
          options.onDestroy.call(this);
        }
      }

      cacheBoundElements() {
        this._bindings.clear();
        this.querySelectorAll("[data-bind]").forEach(el => {
          const key = el.getAttribute("data-bind");
          if (!this._bindings.has(key)) {
            this._bindings.set(key, []);
          }
          this._bindings.get(key).push(el);
        });
      }

      getProps() {
        const props = {};
        for (const attr of this.attributes) {
          props[attr.name] = attr.value;
        }
        return props;
      }

      setState(newState, render = true, key_render = null) {
        const oldState = { ...this.state };
        this.state = { ...this.state, ...newState };

        if (render) {
          const listChanges = this.detectListChanges(oldState, newState);

          if (key_render) {
            this.partialRender(key_render, oldState);
          } else if (listChanges.length > 0) {
            this.render();
          } else {
            this.render();
          }
        }
      }
      detectListChanges(oldState, newState) {
        const changedLists = [];

        Object.keys(newState).forEach(key => {
          if (Array.isArray(newState[key]) &&
            JSON.stringify(oldState[key]) !== JSON.stringify(newState[key])) {
            changedLists.push(key);
          }
        });

        return changedLists;
      }

      emit(eventName, detail = {}) {
        this.dispatchEvent(new CustomEvent(eventName, {
          bubbles: true,
          detail: detail
        }));
      }
      setupModelBindings() {
        if (this.props['data-model']) {
          this.addEventListener('modelChange', (e) => {
            if (e.detail.model === this.props['data-model']) {
              this.updateParentState(e.detail.value);
            }
          });

        }
      }

      updateParentState(value) {
        let parent = this.parentElement;
        while (parent) {
          if (parent.tagName.includes('-') && parent.setState && parent.props) {
            const modelKey = this.props['data-model'];
            if (modelKey) {
              parent.setState({ [modelKey]: value }, false);
            }
            break;
          }
          parent = parent.parentElement;
        }
      }

      partialRender(key, oldState) {
        if (this._bindings.has(key) && this.state[key] !== oldState[key]) {
          this._bindings.get(key).forEach(el => {
            el.textContent = this.state[key];
          });
        }

        if (this.state[key] !== oldState[key]) {
          this.querySelectorAll(`[data-model="${key}"]`).forEach(el => {
            if (el.value !== this.state[key]) {
              el.value = this.state[key];
            }
          });
        }

        this.querySelectorAll(`[data-key="if-${key}"]`).forEach(el => {
          const shouldShow = this.state[key];
          if (shouldShow && el.style.display === 'none') {
            el.style.display = '';
            el.innerHTML = el._originalContent || '';
          } else if (!shouldShow && el.style.display !== 'none') {
            el._originalContent = el.innerHTML;
            el.style.display = 'none';
            el.innerHTML = '';
          }
        });

        if (key.startsWith('items-')) {
          const listName = key.replace('items-', '');
          this.updateDataForList(listName, oldState[listName]);
        }
      }

      updateDataForList(listName, oldItems = []) {
        const newItems = this.state[listName] || [];

        const container = this.querySelector(`[data-for="item in ${listName}"]`);

        if (!container) {
          console.error(`Container not found for list: ${listName}`);
          return;
        }

        if (!container._originalTemplate) {
          container._originalTemplate = container.innerHTML;
          console.log('Template cached:', container._originalTemplate);
        }

        const oldKeys = oldItems.map((_, index) => `${listName}-${index}`);
        const newKeys = newItems.map((_, index) => `${listName}-${index}`);

        console.log('Keys comparison:', { oldKeys, newKeys });

        oldKeys.forEach((oldKey) => {
          if (!newKeys.includes(oldKey)) {
            const elementToRemove = container.querySelector(`[data-key="${oldKey}"]`);
            if (elementToRemove) {
              console.log('Removing element with key:', oldKey);
              elementToRemove.remove();
            }
          }
        });

        newKeys.forEach((newKey, newIndex) => {
          const existingElement = container.querySelector(`[data-key="${newKey}"]`);
          const item = newItems[newIndex];

          if (!existingElement) {
            console.log('Adding new element with key:', newKey);
            this.addNewListItem(container, listName, item, newIndex);
          } else {
            console.log('Updating existing element with key:', newKey);
            this.updateListItem(existingElement, item, newIndex);
          }
        });
      }

      addNewListItem(container, listName, item, index) {
        if (!container._originalTemplate) {
          container._originalTemplate = container.innerHTML;
        }

        const template = container._originalTemplate;
        const key = `${listName}-${index}`;

        console.log('Creating new item:', { item, index, key });

        const newItemContent = template
          .replace(/\${item}/g, item)
          .replace(/\${index}/g, index)
          .replace(/\${key}/g, key)
          .replace(/\${itemId}/g, index);

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = newItemContent;
        const newElement = tempDiv.firstElementChild;

        const allItems = Array.from(container.querySelectorAll(`[data-key^="${listName}-"]`));

        if (index >= allItems.length) {
          container.appendChild(newElement);
        } else {
          const nextElement = allItems.find(el => {
            const elKey = el.getAttribute('data-key');
            const elIndex = parseInt(elKey.split('-')[1]);
            return elIndex >= index;
          });

          if (nextElement) {
            container.insertBefore(newElement, nextElement);
          } else {
            container.appendChild(newElement);
          }
        }

        this.applyEventsToElement(newElement);
      }
      
      updateListItem(element, item, index) {
        element.querySelectorAll('[data-bind]').forEach(el => {
          const bindKey = el.getAttribute('data-bind');
          if (bindKey === 'item') {
            el.textContent = item;
          } else if (bindKey === 'index') {
            el.textContent = index;
          }
        });

        element.querySelectorAll('[data-index]').forEach(el => {
          el.setAttribute('data-index', index);
        });

        element.querySelectorAll('[data-item]').forEach(el => {
          el.setAttribute('data-item', item);
        });
      }

      renderDataForList(el, listName) {
        const items = this.state[listName] || [];
        if (!el._originalTemplate) {
          el._originalTemplate = el.innerHTML;
        }
        const template = el._originalTemplate;

        el.innerHTML = items.map((item, index) => {
          const itemId = item.id ?? index;
          const key = `${listName}-${itemId}`;

          return template
            .replace(/\${item}/g, item)
            .replace(/\${index}/g, index)
            .replace(/\${key}/g, key)
            .replace(/\${itemId}/g, itemId);
        }).join("");

        this.applyEventsToElement(el);
      }

      applyEventsToElement(element) {
        if (options.actions) {
          this.querySelectorAll("*").forEach(el => {
            Array.from(el.attributes).forEach(attr => {
              const match = attr.name.match(/^data-on:(\w+)$/);
              if (match) {
                const eventType = match[1];
                const actionName = attr.value;

                if (this[actionName] && typeof this[actionName] === 'function') {
                  el.addEventListener(eventType, e => {
                    Promise.resolve(this[actionName](e)).catch(console.error);
                  });
                }
              }
            });
          });
        }
      }


      render(key_render = null) {
        if (key_render) {

        }

        this.innerHTML = this.getTemplateContent();

        this.querySelectorAll("[data-for]").forEach(el => {
          const expression = el.getAttribute("data-for");
          const listName = expression.replace("item in ", "").trim();
          this.renderDataForList(el, listName);
        });

        this.querySelectorAll("[data-model]").forEach(el => {
          const key = el.getAttribute("data-model");
          el.value = this.state[key] ?? '';
          el.oninput = e => {
            this.state[key] = e.target.value;
            this.querySelectorAll(`[data-bind="${key}"]`).forEach(bindEl => {
              bindEl.textContent = this.state[key];
            });
          };
        });

        if (options.actions) {
          this.querySelectorAll("*").forEach(el => {
            Array.from(el.attributes).forEach(attr => {
              const match = attr.name.match(/^data-on:(\w+)$/);
              if (match) {
                const eventType = match[1];
                const actionName = attr.value;

                if (this[actionName] && typeof this[actionName] === 'function') {
                  el.addEventListener(eventType, e => {
                    Promise.resolve(this[actionName](e)).catch(console.error);
                  });
                }
              }
            });
          });
        }
        this.cacheBoundElements();
        return Promise.resolve();
      }


      getTemplateContent() {
        let templateWithData = options.template || '';

        templateWithData = templateWithData.replace(/(<[^>]+ data-bind="([^"]+)"[^>]*>)/g,
          (match, fullTag, bindKey) => {
            return fullTag.replace('>', ` data-key="bind-${bindKey}">`);
          }
        );

        templateWithData = templateWithData.replace(/\${props\.(\w+)}/g, (m, p) => {
          return this.props[p] || this.getAttribute(p) || '';
        });

        templateWithData = templateWithData.replace(/\${state\.(\w+)}/g, (m, s) => this.state[s] || '');

        templateWithData = templateWithData.replace(/<([^>]+) data-for="([^"]+)"([^>]*)>([\s\S]*?)<\/\1>/g,
          (match, tag, expression, attributes, content) => {
            const listName = expression.replace("item in ", "").trim();
            const items = this.state[listName] || [];

            return items.map((item, index) => {
              const itemId = item.id ?? index;
              const key = `${listName}-${itemId}`;

              let itemContent = content
                .replace(/\${item}/g, item)
                .replace(/\${index}/g, index)
                .replace(/\${key}/g, key)
                .replace(/\${itemId}/g, itemId);

              return `<${tag}${attributes} data-key="${key}">${itemContent}</${tag}>`;
            }).join("");
          }
        );

        templateWithData = templateWithData.replace(/<([^>]+) data-if="([^"]+)"([^>]*)>([\s\S]*?)<\/\1>/g,
          (match, tag, condition, attributes, content) => {
            if (this.state[condition]) {
              return `<${tag}${attributes} data-key="if-${condition}">${content}</${tag}>`;
            } else {
              return '';
            }
          }
        );

        templateWithData = templateWithData.replace(/<slot><\/slot>/g, this._children);

        return templateWithData;
      }
    }

    customElements.define(name, CustomComponent);
  },

  mount(rootId) {
    this.root = document.getElementById(rootId);
    if (!this.root) {
      console.error(`No se encontró el elemento con id "${rootId}"`);
      return;
    }
    if (!window.location.hash) {
      window.location.hash = "/";
    }

    window.addEventListener("hashchange", () => {
      this.navigate(window.location.hash.slice(1) || "/");
    });
    this.navigate(window.location.hash.slice(1) || "/");
  },

  defineRoute(path, componentFn) {
    this.routes[path] = componentFn;
  },

  navigate(path) {
    if (!this.root) {
      console.error("Use firs App.mount('#id'),Usa App.mount('#id') primero");
      return;
    }

    if (window.location.hash.slice(1) !== path) {
      window.location.hash = path;
    }

    const view = this.routes[path];
    if (view) {
      this.root.innerHTML = view();
    } else {
      if (path !== "/") {
        this.navigate("/");
      } else {
        if (this.routes['/']) this.root.innerHTML = this.routes['/'];
        else {
          this.root.innerHTML = "<h1>404 - Página no encontrada</h1>";
          console.error(`Ruta "${path}" no definida y la ruta "/" tampoco está definida en las rutas:`, this.routes);
        }
      }
    }
  }
};