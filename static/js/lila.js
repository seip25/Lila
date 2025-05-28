const stores = new Map();
const components = new Map();
const currentInstances = new Set();

function getComponents(name) {
    return components.get(name);
}

function reactive(obj, onUpdate = false) {
    const subscribers = new Set();

    if (onUpdate) {
        subscribers.add(onUpdate);
    }

    return new Proxy(obj, {
        set(target, prop, value) {
            if (target[prop] !== value) {
                target[prop] = value;
                subscribers.forEach(cb => cb(prop, value));
            }
            return true;
        },
        get(target, prop) {
            if (prop === 'subscribe') {
                return (callback) => {
                    subscribers.add(callback);
                    return () => subscribers.delete(callback);
                };
            }
            const value = target[prop];

            if (typeof value === 'function' && Array.isArray(target) &&
                ['push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse'].includes(prop)) {
                return function (...args) {
                    const result = value.apply(target, args);
                    subscribers.forEach(cb => cb('items', target));
                    return result;
                }
            }

            return value;
        }
    });
}


function createComponent(name, { template, state, actions, onMount, onDestroy }) {
    const templateFn = typeof template === 'string'
        ? compileTemplate(template)
        : template;
    components.set(name, {
        template: templateFn,
        state: state || (() => ({})),
        actions: actions || {},
        onMount,
        onDestroy
    });
}

function evalInContext(expr, context) {
    try {
        const paramNames = Object.keys(context);
        const paramValues = Object.values(context);
        const result = Function(...paramNames, `return ${expr}`)(...paramValues);
        return result;
    } catch (e) {
        console.error(`Error evaluating expression: "${expr}"`, e);
        return undefined;
    }
}


function mountComponent(name, targetId, props = {}) {
    const target = document.getElementById(targetId);
    if (!target) {
        console.error(`Target element with id "${targetId}" not found.`);
        return null;
    }

    const componentDef = components.get(name);
    if (!componentDef) {
        console.error(`Component "${name}" not found.`);
        return null;
    }

    const state = reactive(componentDef.state(props));
    const boundElements = new Map();
    const nestedComponents = new Map();
    let isUpdating = false;

    function createUniqueId(el) {
        const id = 'lila-' + Math.random().toString(36).substr(2, 9);
        if (document.getElementById(id)) {
            return createUniqueId(el);
        }
        el.id = id;
        return id;
    }

    function getDependencies(expr) {
        const matches = expr.match(/\b(?!(?:true|false|null|undefined|this)\b)[a-zA-Z_$][a-zA-Z0-9_$]*\b/g) || [];
        return matches;
    }

    function renderRepeatSection(templateEl, state, componentDef) {
        const repeatExpr = templateEl.getAttribute('data-repeat');
        const items = evalInContext(repeatExpr, { ...state, ...componentDef.actions });
        const container = templateEl.parentNode;

         

        let currentElement = templateEl.nextElementSibling;
        while (currentElement) {
            const nextElement = currentElement.nextElementSibling;
            if (currentElement && currentElement.hasAttribute('data-repeated-item')) { 
                container.removeChild(currentElement);
            } else {
                break;
            }
            currentElement = nextElement;
        }

        const fragment = document.createDocumentFragment();
        const itemTemplate = templateEl.firstElementChild;

        if (!itemTemplate) {
            console.warn(`data-repeat element "[data-repeat="${repeatExpr}"]" has no child element to use as a template.`);
            templateEl.style.display = 'none';
            return;
        }

        if (Array.isArray(items)) {
            items.forEach((item, index) => {
                const clone = itemTemplate.cloneNode(true);

                clone.setAttribute('data-repeated-item', '');

                clone.querySelectorAll('[data-repeat-bind]').forEach(bindEl => {
                    const bindExpr = bindEl.getAttribute('data-repeat-bind');
                    const repeatContext = { ...state, ...componentDef.actions, item, index };
                    const result = evalInContext(bindExpr, repeatContext);
                    bindEl.textContent = result !== undefined ? result : '';
                });

                clone.querySelectorAll('[data-repeat-action]').forEach(actionEl => {
                    const actionName = actionEl.getAttribute('data-repeat-action');
                    if (componentDef.actions[actionName]) {
                        const listener = (e) => {
                            e.preventDefault();
                            componentDef.actions[actionName]({ state, event: e, item, index });
                        };
                        actionEl.addEventListener('click', listener);
                        actionEl._actionListener = listener;
                    } else {
                        console.warn(`Action "${actionName}" not found for data-repeat-action`);
                    }
                });

                fragment.appendChild(clone);
            });
        } else {
            console.warn(`data-repeat expression "${repeatExpr}" did not evaluate to an array. Result:`, items);
        }

        container.insertBefore(fragment, templateEl.nextSibling); 


        templateEl.style.display = 'none'; 
    }


    function initializeDOMBindings(target, state, componentDef) {

        target.querySelectorAll('[data-if]').forEach(el => {
            const condition = el.getAttribute('data-if');
            const shouldShow = evalInContext(condition, { ...state, ...componentDef.actions });
            el.style.display = shouldShow ? '' : 'none';
        });

        target.querySelectorAll('[data-else]').forEach(el => {
            const condition = el.getAttribute('data-else');
            const shouldShow = evalInContext(condition, { ...state, ...componentDef.actions });
            el.style.display = !shouldShow ? '' : 'none';
        });

        target.querySelectorAll('[data-repeat]').forEach(templateEl => {
            renderRepeatSection(templateEl, state, componentDef);
        });


        target.querySelectorAll('[data-component]').forEach(el => {
            const targetId = el.id || createUniqueId(el);
            el.id = targetId;
            if (!el._componentInstance) {
                const componentName = el.dataset.component;
                const nestedComponent = mountComponent(componentName, targetId);
                if (nestedComponent) {
                    nestedComponents.set(el, nestedComponent);
                    el._componentInstance = nestedComponent;
                }
            }
        });


        target.querySelectorAll('[data-action]').forEach(el => {
            const actionName = el.dataset.action;
            if (componentDef.actions[actionName] && !el._actionListener) {
                const listener = (e) => {
                    if (el.tagName === 'FORM') e.preventDefault();
                    componentDef.actions[actionName]({ state, event: e });
                };
                const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
                el.addEventListener(eventType, listener);
                el._actionListener = listener;
            } else if (!componentDef.actions[actionName]) {
                console.warn(`Action "${actionName}" not found for data-action`);
            }
        });

        target.querySelectorAll('[data-model]').forEach(input => {
            const property = input.getAttribute('data-model');
            if (state[property] !== undefined) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    input.checked = state[property];
                } else {
                    input.value = state[property];
                }
            } else {
            }

            if (!boundElements.has(input)) {
                const eventType = (input.type === 'checkbox' || input.type === 'radio') ? 'change' : 'input';
                const listener = (e) => {
                    if (!isUpdating) {
                        if (input.type === 'checkbox') {
                            state[property] = e.target.checked;
                        } else if (input.type === 'radio') {
                            if (e.target.checked) {
                                state[property] = e.target.value;
                            }
                        }
                        else {
                            state[property] = e.target.value;
                        }
                    }
                };
                input.addEventListener(eventType, listener);
                boundElements.set(input, { property, listener, eventType });
            }
        });

        target.querySelectorAll('[data-bind]').forEach(el => {
            const property = el.getAttribute('data-bind');
            if (state[property] !== undefined) el.textContent = state[property];
        });
    }


    function update(onlyTheseProps = []) {
        if (isUpdating || !target) return;
        isUpdating = true;

        requestAnimationFrame(() => {
            try {
                if (onlyTheseProps.length === 0) {
                    boundElements.forEach(({ listener, eventType }, input) => {
                        if (input && listener) input.removeEventListener(eventType, listener);
                    });
                    boundElements.clear();
                    target.querySelectorAll('[data-action]').forEach(el => {
                        if (el._actionListener) {
                            const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
                            el.removeEventListener(eventType, el._actionListener);
                            delete el._actionListener;
                        }
                    });
                    nestedComponents.forEach((instance, el) => {
                        try { instance.destroy(); } catch (e) { console.error('Error destroying nested component during update:', e); }
                        if (el) delete el._componentInstance;
                    });
                    nestedComponents.clear();


                    const html = componentDef.template({ ...state, ...componentDef.actions });
                    if (typeof html === 'string') {
                        target.innerHTML = html;

                        initializeDOMBindings(target, state, componentDef);
                    } else {
                        console.error("Component template did not return a string.");
                    }

                } else {
                    onlyTheseProps.forEach(prop => {
                        target.querySelectorAll(`[data-bind="${prop}"]`).forEach(el => {
                            if (state[prop] !== undefined) el.textContent = state[prop];
                        });

                        target.querySelectorAll(`[data-model="${prop}"]`).forEach(input => {
                            if (input !== document.activeElement && state[prop] !== undefined) {
                                if (input.type === 'checkbox' || input.type === 'radio') {
                                    if (input.checked !== state[prop]) input.checked = state[prop];
                                } else {
                                    if (input.value !== state[prop]) input.value = state[prop];
                                }
                            }
                        });
                        target.querySelectorAll('[data-if]').forEach(el => {
                            const condition = el.getAttribute('data-if');
                            const dependencies = getDependencies(condition);
                            if (dependencies.includes(prop)) {
                                const shouldShow = evalInContext(condition, { ...state, ...componentDef.actions });
                                el.style.display = shouldShow ? '' : 'none';
                            }
                        });

                        target.querySelectorAll('[data-else]').forEach(el => {
                            const condition = el.getAttribute('data-else');
                            const dependencies = getDependencies(condition);
                            if (dependencies.includes(prop)) {
                                const shouldShow = evalInContext(condition, { ...state, ...componentDef.actions });
                                el.style.display = !shouldShow ? '' : 'none';
                            }
                        });

                        target.querySelectorAll('[data-repeat]').forEach(templateEl => {
                            const repeatExpr = templateEl.getAttribute('data-repeat');
                            const dependencies = getDependencies(repeatExpr);

                            if (dependencies.includes(prop)) {
                                renderRepeatSection(templateEl, state, componentDef);
                            }
                        });
                    });
                }
            } catch (error) {
                console.error('Error during update:', error);
            } finally {
                isUpdating = false;
            }
        });
    }


    const unsubscribe = state.subscribe((prop) => {
        update([prop]);
    });


    setTimeout(() => { 
        update();

        if (componentDef.onMount) {
            try { 
                const result = componentDef.onMount(state);
                if (result && typeof result.then === 'function') {
                    result.then(() => { 
                        update();
                    }).catch(error => console.error('Error in onMount promise:', error));
                } else { 
                    update();
                }
            } catch (error) {
                console.error('Error in onMount:', error);
            }
        }
    }, 0);


    const componentInstance = {
        destroy: () => { 
            try {
                if (componentDef.onDestroy) componentDef.onDestroy(state);
            } catch (error) {
                console.error('Error in onDestroy:', error);
            }

            nestedComponents.forEach((instance, el) => {
                try {
                    instance.destroy();
                    if (el) delete el._componentInstance;
                } catch (error) {
                    console.error('Error destroying nested component:', error);
                }
            });
            nestedComponents.clear();

            unsubscribe();

            boundElements.forEach(({ listener, eventType }, input) => {
                if (input && listener) {
                    input.removeEventListener(eventType, listener);
                }
            });
            boundElements.clear();

            if (target) {
                target.querySelectorAll('[data-action]').forEach(el => {
                    if (el._actionListener) {
                        const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
                        el.removeEventListener(eventType, el._actionListener);
                        delete el._actionListener;
                    }
                });
                target.innerHTML = '';
            }
        },
        state,
        forceUpdate: () => { 
            update();
        }
    };

    currentInstances.add(componentInstance);
    return componentInstance;
}

function handleRouting() {
    const path = window.location.hash.substring(1) || '/';
    const route = routes.get(path) || routes.get('*');

    if (!route) {
        console.warn(`No route found for path: "${path}"`);
        return;
    }

    currentInstances.forEach(instance => {
        try {
            instance.destroy();
        } catch (error) {
            console.error('Error destroying instance during routing:', error);
        }
    });
    currentInstances.clear();

    const outlet = document.getElementById('app-lila');
    if (outlet) {
        mountComponent(route.componentName, 'app-lila', route.props);
    } else {
        console.error('App outlet element with id "app-lila" not found.');
    }
}

const routes = new Map();

function addRoute(path, componentName, props = {}) {
    routes.set(path, { componentName, props });
}

function navigateTo(path) {
    if (window.location.hash.substring(1) !== path) {
        window.location.hash = path;
    }
}

function compileTemplate(templateId) {
    const templateElement = document.querySelector(`[data-template="${templateId}"]`);
    if (!templateElement) {
        console.error(`Template element with data-template="${templateId}" not found.`);
        return () => '';
    }

    const html = templateElement.innerHTML;

    return (data) => {
        return html.replace(/\${([^}]+)}/g, (match, expr) => {
            try {
                return evalInContext(expr.trim(), data);
            } catch (e) {
                console.error(`Error evaluating template expression: "${expr}"`, e);
                return `Error: ${expr}`;
            }
        });
    };
}

window.addEventListener('hashchange', handleRouting);
window.addEventListener('load', handleRouting);

document.addEventListener('click', e => {
    const linkEl = e.target.closest('[data-link]');
    if (linkEl) {
        e.preventDefault();
        const path = linkEl.getAttribute('href');
        if (path) {
            navigateTo(path);
        }
    }
});

window.App = {
    reactive,
    createComponent,
    addRoute,
    navigateTo,
    mountComponent,
    getComponents,
    evalInContext
};