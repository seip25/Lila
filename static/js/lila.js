const stores = new Map();
const components = new Map();
const currentInstances = new Set();

function getComponents(name) {
    return components.get(name);
}

function reactive(obj) {
    const subscribers = new Set();

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
            return target[prop];
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
        return Function(...Object.keys(context), `return ${expr}`)(...Object.values(context));
    } catch (e) {
        console.error(`Error evaluating expression: ${expr}`, e);
        return false;
    }
}

function mountComponent(name, targetId, props = {}) {
    const target = document.getElementById(targetId);
    if (!target) {
        console.error(`Target element with id "${targetId}" not found`);
        return null;
    }

    const componentDef = components.get(name);
    if (!componentDef) {
        console.error(`Component "${name}" not found`);
        return null;
    }

    const state = reactive(componentDef.state(props));
    const boundElements = new Map();
    const nestedComponents = new Map();
    let isUpdating = false;

    function createUniqueId(el) {
        const id = 'nested-' + Math.random().toString(36).substr(2, 9);
        el.id = id;
        return id;
    }

    function update(onlyTheseProps = []) {
        if (isUpdating || !target) return;
        isUpdating = true;

        try {
            if (onlyTheseProps.length === 0) {
                const html = componentDef.template({ ...state, ...componentDef.actions });
                if (typeof html === 'string') {
                    target.innerHTML = html;
 
                    target.querySelectorAll('[data-if]').forEach(el => {
                        const condition = el.getAttribute('data-if');
                        const shouldShow = evalInContext(condition, { ...state, ...componentDef.actions });
                        el.style.display = shouldShow ? '' : 'none';
                    });

                    target.querySelectorAll('[data-component]').forEach(el => {
                        const componentName = el.dataset.component;
                        const nestedComponent = mountComponent(componentName, el.id || createUniqueId(el));
                        if (nestedComponent) {
                            nestedComponents.set(el, nestedComponent);
                        }
                    });

                    target.querySelectorAll('[data-action]').forEach(el => {
                        const actionName = el.dataset.action;
                        if (componentDef.actions[actionName] && !el._actionListener) {
                            const listener = (e) => {
                                if (e.target.tagName === 'FORM') {
                                    e.preventDefault();
                                }
                                componentDef.actions[actionName]({ state, event: e });
                            };

                            const eventType = el.tagName === 'FORM' ? 'submit' : 'click';
                            el.addEventListener(eventType, listener);
                            el._actionListener = listener;
                        }
                    });

                    target.querySelectorAll('[data-model]').forEach(input => {
                        const property = input.getAttribute('data-model');
                        if (input.value !== state[property]) {
                            input.value = state[property];
                        }

                        if (!boundElements.has(input)) {
                            const listener = (e) => {
                                if (!isUpdating && state[property] !== e.target.value) {
                                    state[property] = e.target.value;
                                }
                            };
                            input.addEventListener('input', listener);
                            boundElements.set(input, { property, listener });
                        }
                    });

                    target.querySelectorAll('[data-bind]').forEach(el => {
                        const property = el.getAttribute('data-bind');
                        if (state[property] !== undefined) {
                            el.textContent = state[property];
                        }
                    });
                }
            } else {
                onlyTheseProps.forEach(prop => {
                    target.querySelectorAll(`[data-bind="${prop}"]`).forEach(el => {
                        el.textContent = state[prop];
                    });

                    target.querySelectorAll(`[data-model="${prop}"]`).forEach(input => {
                        if (input !== document.activeElement && input.value !== state[prop]) {
                            input.value = state[prop];
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
                });
            }
        } catch (error) {
            console.error('Error during update:', error);
        } finally {
            isUpdating = false;
        }
    }

    function getDependencies(expr) {
        const matches = expr.match(/\b[a-zA-Z_$][a-zA-Z0-9_$]*\b/g) || [];
        return matches.filter(m => !['true', 'false', 'null', 'undefined'].includes(m));
    }

    const unsubscribe = state.subscribe((prop) => {
        update([prop]);
    });

    update();

    if (componentDef.onMount) {
        setTimeout(() => {
            try {
                const result = componentDef.onMount(state);
                if (result && typeof result.then === 'function') {
                    result.then(() => update());
                } else {
                    update();
                }
            } catch (error) {
                console.error('Error in onMount:', error);
            }
        }, 0);
    }

    const componentInstance = {
        destroy: () => {
            try {
                if (componentDef.onDestroy) {
                    componentDef.onDestroy(state);
                }
            } catch (error) {
                console.error('Error in onDestroy:', error);
            }

            nestedComponents.forEach(instance => {
                try {
                    instance.destroy();
                } catch (error) {
                    console.error('Error destroying nested component:', error);
                }
            });
            nestedComponents.clear();

            unsubscribe();
            boundElements.forEach(({ listener }, input) => {
                input?.removeEventListener('input', listener);
            });
            boundElements.clear();

            if (target) {
                target.querySelectorAll('[data-action]').forEach(el => {
                    if (el._actionListener) {
                        el.removeEventListener('click', el._actionListener);
                    }
                });
                target.innerHTML = '';
            }
        },
        state,
        forceUpdate: () => update()
    };

    currentInstances.add(componentInstance);
    return componentInstance;
}

function handleRouting() {
    const path = window.location.hash.substring(1) || '/';
    const route = routes.get(path) || routes.get('*');

    if (!route) {
        console.error(`Route not found: ${path}`);
        return;
    }

    currentInstances.forEach(instance => {
        try {
            instance.destroy();
        } catch (error) {
            console.error('Error destroying instance:', error);
        }
    });
    currentInstances.clear();

    const outlet = document.getElementById('app-lila');
    if (outlet) {
        mountComponent(route.componentName, 'app-lila', route.props);
    } else {
        console.error('Router outlet not found');
    }
}

const routes = new Map();

function addRoute(path, componentName, props = {}) {
    routes.set(path, { componentName, props });
}

function navigateTo(path) {
    window.location.hash = path;
}

function compileTemplate(templateId) {
    const templateElement = document.querySelector(`[data-template="${templateId}"]`);
    if (!templateElement) {
        console.error(`Template with ID "${templateId}" not found`);
        return () => '';
    }

    const html = templateElement.innerHTML;

    return (data) => {
        return html.replace(/\${([^}]+)}/g, (match, prop) => {
            return data[prop.trim()] || '';
        });
    };
}

window.addEventListener('hashchange', handleRouting);
document.addEventListener('click', e => {
    if (e.target.matches('[data-link]')) {
        e.preventDefault();
        navigateTo(e.target.getAttribute('href'));
    }
});

window.App = {
    reactive,
    createComponent,
    addRoute,
    navigateTo,
    mountComponent,
    getComponents
};