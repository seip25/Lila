// English: Global maps to store component definitions and instances.
// Español: Mapas globales para almacenar definiciones e instancias de componentes.
const componentStores = new Map();
const registeredComponents = new Map();
const activeComponentInstances = new Set();

// English: Retrieves a registered component definition.
// Español: Recupera la definición de un componente registrado.
function getRegisteredComponents(componentName) {
    return registeredComponents.get(componentName);
}

// English: Creates a reactive object using a Proxy.
// Español: Crea un objeto reactivo usando un Proxy.
function reactive(data, callback = false) {
    let dependencySet = new Set();
    if (callback) {
        dependencySet.add(callback);
    }
    return new Proxy(data, {
        // English: The set trap is called when a property is set.
        // Español: El trap 'set' se llama cuando se establece una propiedad.
        set: (target, property, value) => {
            if (target[property] !== value) {
                target[property] = value;
                // English: Notify all dependent effects of the change.
                // Español: Notifica a todos los efectos dependientes sobre el cambio.
                dependencySet.forEach(effect => effect(property, value));
            }
            return true;
        },
        // English: The get trap is called when a property is accessed.
        // Español: El trap 'get' se llama cuando se accede a una propiedad.
        get(target, property) {
            if (property === "subscribe") {
                return (effect) => {
                    dependencySet.add(effect);
                    // English: Returns an unsubscribe function.
                    // Español: Devuelve una función para desuscribirse.
                    return () => dependencySet.delete(effect);
                };
            }
            let result = target[property];
            // English: Intercept array mutation methods to trigger reactivity.
            // Español: Intercepta los métodos de mutación de arrays para activar la reactividad.
            if (typeof result === "function" && Array.isArray(target) && [
                "push",
                "pop",
                "shift",
                "unshift",
                "splice",
                "sort",
                "reverse"
            ].includes(property)) {
                return function (...args) {
                    let methodResult = result.apply(target, args);
                    dependencySet.forEach(effect => effect("items", target));
                    return methodResult;
                };
            }
            return result;
        }
    });
}

// English: Registers a new component definition.
// Español: Registra una nueva definición de componente.
function createComponent(name, {
    template,
    state,
    actions,
    onMount,
    onDestroy
}) {
    // English: Compile the template if it's a string ID.
    // Español: Compila la plantilla si es un ID de cadena.
    let compiledTemplate = typeof template === "string" ? compileTemplate(template) : template;
    registeredComponents.set(name, {
        template: compiledTemplate,
        state: state || (() => ({})),
        actions: actions || {},
        onMount: onMount,
        onDestroy: onDestroy
    });
    return registeredComponents.get(name);
}

// English: Evaluates an expression in a given context.
// Español: Evalúa una expresión en un contexto dado.
function evalInContext(expression, context) {
    try {
        let keys = Object.keys(context);
        let values = Object.values(context);
        let evaluationFunction = new Function(...keys, `return ${expression}`);
        let result = evaluationFunction(...values);
        return result;
    } catch (error) {
        console.error(`Error evaluating expression: "${expression}"`, error);
        return;
    }
}

// English: Mounts a component into a target DOM element.
// Español: Monta un componente en un elemento DOM de destino.
function mountComponent(componentName, targetElementId, props = {}) {
    let targetElement = document.getElementById(targetElementId);
    if (!targetElement) {
        console.error(`Target element with id "${targetElementId}" not found.`);
        return null;
    }

    let componentDefinition = registeredComponents.get(componentName);
    if (!componentDefinition) {
        console.error(`Component "${componentName}" not found.`);
        return null;
    }

    // English: Create a reactive state for the component instance.
    // Español: Crea un estado reactivo para la instancia del componente.
    let componentState = reactive(componentDefinition.state(props));
    let modelListeners = new Map();
    let nestedComponentInstances = new Map();
    let isUpdating = false;

    // English: Capture the content of the target element to be used as a slot.
    // Español: Captura el contenido del elemento de destino para usarlo como un slot.
    const slotContent = document.createDocumentFragment();
    while (targetElement.firstChild) {
        slotContent.appendChild(targetElement.firstChild);
    }

    // English: Extracts dependencies from an expression string.
    // Español: Extrae las dependencias de una cadena de expresión.
    function getExpressionDependencies(expression) {
        const reserved = new Set(['true', 'false', 'null', 'undefined', 'this']);
        return [...new Set((expression.match(/[a-zA-Z_$][a-zA-Z0-9_$]*/g) || [])
            .filter(dep => !reserved.has(dep)))];
    }

    // English: Renders elements for a data-repeat directive.
    // Español: Renderiza elementos para una directiva data-repeat.
    function renderRepeatElements(repeatElement, context, componentActions) {
        let repeatExpression = repeatElement.getAttribute("data-repeat");
        let repeatData = evalInContext(repeatExpression, {
            ...context,
            ...componentActions
        });
        let parentElement = repeatElement.parentNode;
        let nextSibling = repeatElement.nextElementSibling;

        // English: Clear previously rendered items.
        // Español: Limpia los elementos renderizados previamente.
        while (nextSibling) {
            let currentSibling = nextSibling;
            nextSibling = currentSibling.nextElementSibling;
            if (currentSibling && currentSibling.hasAttribute("data-repeated-item")) {
                parentElement.removeChild(currentSibling);
            } else {
                break;
            }
        }

        let fragment = document.createDocumentFragment();
        let templateElement = repeatElement.firstElementChild;

        if (!templateElement) {
            console.warn(`data-repeat element "[data-repeat="${repeatExpression}"]" has no child element to use as a template.`);
            repeatElement.style.display = "none";
            return;
        }

        if (Array.isArray(repeatData)) {
            repeatData.forEach((item, index) => {
                let repeatedItemElement = templateElement.cloneNode(true);
                repeatedItemElement.setAttribute("data-repeated-item", "");

                // English: Handle conditional rendering within repeated items.
                // Español: Maneja el renderizado condicional dentro de los elementos repetidos.
                repeatedItemElement.querySelectorAll("[data-repeat-if]").forEach(ifElement => {
                    let ifExpression = ifElement.getAttribute("data-repeat-if");
                    let dependencies = getExpressionDependencies(ifExpression);

                    let showElement = evalInContext(ifExpression, {
                        ...context,
                        ...componentActions,
                        item: item,
                        index: index
                    });
                    ifElement.style.display = showElement ? "" : "none";
                    if (dependencies.includes("item")) {
                        showElement = evalInContext(ifExpression, {
                            ...context,
                            ...componentActions,
                            item: item,
                            index: index
                        });
                        ifElement.style.display = showElement ? "" : "none";
                    }

                });

                // English: Handle HTML attribute binding.
                // Español: Maneja el enlace de atributos HTML.
                repeatedItemElement.querySelectorAll('*').forEach(el => {
                    Array.from(el.attributes)
                        .filter(attr => attr.name.startsWith('data-repeat-bind-html-'))
                        .forEach(attr => {
                            const htmlAttr = attr.name.replace('data-repeat-bind-html-', '');
                            const expression = attr.value;
                            const value = evalInContext(expression, { ...context, item, index });

                            if (value !== undefined && value !== null) {
                                el.setAttribute(htmlAttr, value);
                            }
                        });
                });

                // English: Handle text content binding.
                // Español: Maneja el enlace de contenido de texto.
                Array.from(repeatedItemElement.querySelectorAll('[data-repeat-bind]')).forEach(el => {
                    const textBinding = el.getAttribute('data-repeat-bind');
                    if (textBinding) {
                        const value = evalInContext(textBinding, { ...context, item, index });
                        if (value !== undefined) {
                            el.textContent = value;
                        }
                    }

                    Array.from(el.attributes).forEach(attr => {
                        if (attr.name.startsWith('data-repeat-bind:')) {
                            const attributeName = attr.name.split(':')[1];
                            const expression = attr.value;
                            const value = evalInContext(expression, { ...context, item, index });

                            if (value !== undefined) {
                                el.setAttribute(attributeName, value);
                            }

                        }
                    });
                });

                // English: Handle action binding for repeated items.
                // Español: Maneja el enlace de acciones para elementos repetidos.
                repeatedItemElement.querySelectorAll("[data-repeat-action]").forEach(actionElement => {
                    let actionName = actionElement.getAttribute("data-repeat-action");
                    if (componentActions[actionName]) {
                        let eventListener = (event) => {
                            event.preventDefault();
                            componentActions[actionName]({
                                state: context,
                                event: event,
                                item: item,
                                index: index
                            });
                        };
                        actionElement.addEventListener("click", eventListener);
                        actionElement._actionListener = eventListener;
                    } else {
                        console.warn(`Action "${actionName}" not found for data-repeat-action`);
                    }
                });

                fragment.appendChild(repeatedItemElement);
            });
        } else {
            console.warn(`data-repeat expression "${repeatExpression}" did not evaluate to an array. Result:`, repeatData);
        }
        parentElement.insertBefore(fragment, repeatElement.nextSibling);
        repeatElement.style.display = "none";
    }

    // English: Updates the view based on state changes.
    // Español: Actualiza la vista en función de los cambios de estado.
    function updateView(changedProperties = []) {

        if (isUpdating || !targetElement) {
            return;
        }
        isUpdating = true;
        requestAnimationFrame(() => {
            try {
                // English: Full render if no specific properties are changed.
                // Español: Renderizado completo si no se cambian propiedades específicas.
                if (changedProperties.length === 0) {
                    // English: Clean up old listeners and instances.
                    // Español: Limpia los antiguos listeners e instancias.
                    modelListeners.forEach(({
                        listener,
                        eventType
                    }, element) => {
                        if (element && listener) {
                            element.removeEventListener(eventType, listener);
                        }
                    });
                    modelListeners.clear();

                    targetElement.querySelectorAll("[data-action]").forEach(actionElement => {
                        if (actionElement._actionListener) {
                            let eventType = actionElement.tagName === "FORM" ? "submit" : "click";
                            actionElement.removeEventListener(eventType, actionElement._actionListener);
                            delete actionElement._actionListener;
                        }
                    });

                    nestedComponentInstances.forEach((instance, element) => {
                        try {
                            instance.destroy();
                        } catch (error) {
                            console.error("Error destroying nested component during update:", error);
                        }
                        if (element) {
                            delete element._componentInstance;
                        }
                    });
                    nestedComponentInstances.clear();

                    let renderedTemplate = componentDefinition.template({
                        ...componentState,
                        ...componentDefinition.actions
                    });

                    if (typeof renderedTemplate === "string") {
                        targetElement.innerHTML = renderedTemplate;

                        // English: Find the slot element in the component's template.
                        // Español: Encuentra el elemento slot en la plantilla del componente.
                        const slotOutlet = targetElement.querySelector('slot');

                        // English: If a slot element exists and there is content to insert,
                        // replace the slot with the content.
                        // Español: Si existe un elemento slot y hay contenido para insertar,
                        // reemplaza el slot con el contenido.
                        if (slotOutlet && slotContent.hasChildNodes()) {
                            slotOutlet.parentNode.replaceChild(slotContent, slotOutlet);
                        }

                        // English: Handle conditional rendering.
                        // Español: Maneja el renderizado condicional.
                        targetElement.querySelectorAll("[data-if]").forEach(ifElement => {
                            let ifExpression = ifElement.getAttribute("data-if");
                            let showElement = evalInContext(ifExpression, {
                                ...componentState,
                                ...componentDefinition.actions
                            });
                            ifElement.style.display = showElement ? "" : "none";
                        });

                        targetElement.querySelectorAll("[data-else]").forEach(elseElement => {
                            let elseExpression = elseElement.getAttribute("data-else");
                            let showElement = evalInContext(elseExpression, {
                                ...componentState,
                                ...componentDefinition.actions
                            });
                            elseElement.style.display = showElement ? "none" : "";
                        });

                        // English: Handle list rendering.
                        // Español: Maneja el renderizado de listas.
                        targetElement.querySelectorAll("[data-repeat]").forEach(repeatElement => {
                            renderRepeatElements(repeatElement, componentState, componentDefinition.actions);
                        });

                        // English: Mount nested components.
                        // Español: Monta componentes anidados.
                        targetElement.querySelectorAll("[data-component]").forEach(nestedComponentElement => {
                            let elementId = nestedComponentElement.id || (() => {
                                let id = "lila-" + Math.random().toString(36).substr(2, 9);
                                while (document.getElementById(id)) {
                                    id = "lila-" + Math.random().toString(36).substr(2, 9);
                                }
                                nestedComponentElement.id = id;
                                return id;
                            })();
                            nestedComponentElement.id = elementId;

                            if (!nestedComponentElement._componentInstance) {
                                let nestedComponentName = nestedComponentElement.dataset.component;

                                // English: Wrap parent actions to pass to the child.
                                // Español: Envuelve las acciones del padre para pasarlas al hijo.
                                const wrappedParentActions = {};
                              
                                for (const actionName in componentDefinition.actions) {
                                    if (typeof componentDefinition.actions[actionName] === 'function') {
                                        wrappedParentActions[actionName] = (...args) => {
                                           
                                            return componentDefinition.actions[actionName]({
                                                state: componentState,
                                                actions: componentDefinition.actions,
                                                ...args[0] 
                                            });
                                        };
                                    }
                                }

                                const nestedProps = {
                                    ...evalInContext(nestedComponentElement.dataset.props || '{}', {
                                        ...componentState, 
                                        ...componentDefinition.actions 
                                    }),
                                    _parentActions: wrappedParentActions ,
                                    _parentState: componentState
                                };
                                if(nestedComponentName=='DialogSearch') console.log(`Mounting nested component ${nestedComponentName}: passing props`, nestedProps); 

                                let nestedInstance = mountComponent(nestedComponentName, elementId, nestedProps);


                                if (nestedInstance) {
                                    nestedComponentInstances.set(nestedComponentElement, nestedInstance);
                                    nestedComponentElement._componentInstance = nestedInstance;
                                }
                            }
                        });

                        // English: Set up action listeners.
                        // Español: Configura los listeners de acciones.
                        targetElement.querySelectorAll("[data-action]").forEach(actionElement => {
                            let actionName = actionElement.dataset.action;
                            if (componentDefinition.actions[actionName] && !actionElement._actionListener) {
                                let eventListener = (event) => {
                                    if (actionElement.tagName === "FORM") {
                                        event.preventDefault();
                                    }
                                    componentDefinition.actions[actionName]({
                                        state: componentState,
                                        event: event
                                    });
                                };
                                let eventType = actionElement.tagName === "FORM" ? "submit" : "click";
                                actionElement.addEventListener(eventType, eventListener);
                                actionElement._actionListener = eventListener;
                            } else if (!componentDefinition.actions[actionName]) {
                                console.warn(`Action "${actionName}" not found for data-action`);
                            }
                        });

                        // English: Set up two-way data binding.
                        // Español: Configura el enlace de datos bidireccional.
                        targetElement.querySelectorAll("[data-model]").forEach(modelElement => {
                            let modelProperty = modelElement.getAttribute("data-model");
                            if (componentState[modelProperty] !== undefined) {
                                if (modelElement.type === "checkbox" || modelElement.type === "radio") {
                                    modelElement.checked = componentState[modelProperty];
                                } else {
                                    modelElement.value = componentState[modelProperty];
                                }
                            }
                            if (!modelListeners.has(modelElement)) {
                                let eventType = modelElement.type === "checkbox" || modelElement.type === "radio" ? "change" : "input";
                                let eventListener = (event) => {
                                    if (!isUpdating) {
                                        if (modelElement.type === "checkbox") {
                                            componentState[modelProperty] = event.target.checked;
                                        } else if (modelElement.type === "radio") {
                                            if (event.target.checked) {
                                                componentState[modelProperty] = event.target.value;
                                            }
                                        } else {
                                            componentState[modelProperty] = event.target.value;
                                        }
                                    }
                                };
                                modelElement.addEventListener(eventType, eventListener);
                                modelListeners.set(modelElement, {
                                    property: modelProperty,
                                    listener: eventListener,
                                    eventType: eventType
                                });
                            }
                        });

                        // English: Set up one-way data binding.
                        // Español: Configura el enlace de datos unidireccional.
                        targetElement.querySelectorAll("[data-bind]").forEach(bindElement => {
                            let bindProperty = bindElement.getAttribute("data-bind");
                            if (componentState[bindProperty] !== undefined) {
                                bindElement.textContent = componentState[bindProperty];
                            }
                        });

                    } else {
                        console.error("Component template did not return a string.");
                    }

                } else {
                    // English: Partial update for specific properties.
                    // Español: Actualización parcial para propiedades específicas.
                    changedProperties.forEach(changedProperty => {
                        targetElement.querySelectorAll(`[data-bind="${changedProperty}"]`).forEach(bindElement => {
                            if (componentState[changedProperty] !== undefined) {
                                bindElement.textContent = componentState[changedProperty];
                            }
                        });

                        targetElement.querySelectorAll(`[data-model="${changedProperty}"]`).forEach(modelElement => {
                            if (modelElement !== document.activeElement && componentState[changedProperty] !== undefined) {
                                if (modelElement.type === "checkbox" || modelElement.type === "radio") {
                                    if (modelElement.checked !== componentState[changedProperty]) {
                                        modelElement.checked = componentState[changedProperty];
                                    }
                                } else {
                                    if (modelElement.value !== componentState[changedProperty]) {
                                        modelElement.value = componentState[changedProperty];
                                    }
                                }
                            }
                        });

                        targetElement.querySelectorAll("[data-if]").forEach(ifElement => {
                            let ifExpression = ifElement.getAttribute("data-if");
                            let dependencies = getExpressionDependencies(ifExpression);
                            if (dependencies.includes(changedProperty)) {
                                let showElement = evalInContext(ifExpression, {
                                    ...componentState,
                                    ...componentDefinition.actions
                                });
                                ifElement.style.display = showElement ? "" : "none";
                            }
                        });

                        targetElement.querySelectorAll("[data-else]").forEach(elseElement => {
                            let elseExpression = elseElement.getAttribute("data-else");
                            let dependencies = getExpressionDependencies(elseExpression);
                            if (dependencies.includes(changedProperty)) {
                                let showElement = evalInContext(elseExpression, {
                                    ...componentState,
                                    ...componentDefinition.actions
                                });
                                elseElement.style.display = showElement ? "none" : "";
                            }
                        });

                        targetElement.querySelectorAll("[data-repeat]").forEach(repeatElement => {
                            let repeatExpression = repeatElement.getAttribute("data-repeat");
                            let dependencies = getExpressionDependencies(repeatExpression);
                            if (dependencies.includes(changedProperty)) {
                                renderRepeatElements(repeatElement, componentState, componentDefinition.actions);
                            }
                        });


                    });
                }
            } catch (error) {
                console.error("Error during update:", error);
            } finally {
                isUpdating = false;
            }
        });
    }


    // English: Subscribe to state changes to trigger view updates.
    // Español: Suscríbete a los cambios de estado para activar las actualizaciones de la vista.
    let stateSubscription = componentState.subscribe(property => {
        updateView([property]);
    });

    // English: Perform initial render and call onMount hook.
    // Español: Realiza el renderizado inicial y llama al hook onMount.
    setTimeout(() => {
        updateView();
        if (componentDefinition.onMount) {
            try {
                let onMountResult = componentDefinition.onMount(componentState);
                if (onMountResult && typeof onMountResult.then === "function") {
                    onMountResult.then(() => {
                        updateView();
                    }).catch(error => console.error("Error in onMount promise:", error));
                } else {
                    updateView();
                }
            } catch (error) {
                console.error("Error in onMount:", error);
            }
        }
    }, 0);

    // English: The component instance object.
    // Español: El objeto de la instancia del componente.
    let componentInstance = {
        // English: Destroys the component instance, cleaning up listeners and DOM elements.
        // Español: Destruye la instancia del componente, limpiando listeners y elementos del DOM.
        destroy() {
            try {
                if (componentDefinition.onDestroy) {
                    componentDefinition.onDestroy(componentState);
                }
            } catch (error) {
                console.error("Error in onDestroy:", error);
            }

            nestedComponentInstances.forEach((instance, element) => {
                try {
                    instance.destroy();
                    if (element) {
                        delete element._componentInstance;
                    }
                } catch (error) {
                    console.error("Error destroying nested component:", error);
                }
            });
            nestedComponentInstances.clear();

            stateSubscription();

            modelListeners.forEach(({
                listener,
                eventType
            }, element) => {
                if (element && listener) {
                    element.removeEventListener(eventType, listener);
                }
            });
            modelListeners.clear();

            if (targetElement) {
                targetElement.querySelectorAll("[data-action]").forEach(actionElement => {
                    if (actionElement._actionListener) {
                        let eventType = actionElement.tagName === "FORM" ? "submit" : "click";
                        actionElement.removeEventListener(eventType, actionElement._actionListener);
                        delete actionElement._actionListener;
                    }
                });
                targetElement.innerHTML = "";
            }
        },
        state: componentState,
        forceUpdate() {
            updateView();
        }
    };

    activeComponentInstances.add(componentInstance);

    return componentInstance;
}

// English: Handles routing based on the current URL hash.
// Español: Maneja el enrutamiento basado en el hash de la URL actual.
function handleRouting() {
    let currentHash = window.location.hash.substring(1) || "/";
    let targetRoute = routes.get(currentHash) || routes.get("*");

    if (!targetRoute) {
        console.warn(`No route found for path: "${currentHash}"`);
        return;
    }

    // English: Destroy all active component instances before mounting a new one.
    // Español: Destruye todas las instancias de componentes activas antes de montar una nueva.
    activeComponentInstances.forEach(instance => {
        try {
            instance.destroy();
        } catch (error) {
            console.error("Error destroying instance during routing:", error);
        }
    });
    activeComponentInstances.clear();

    let appOutletElement = document.getElementById("app-lila");
    if (appOutletElement) {
        mountComponent(targetRoute.componentName, "app-lila", targetRoute.props);
    } else {
        console.error('App outlet element with id "app-lila" not found.');
    }
}

// English: Map to store route definitions.
// Español: Mapa para almacenar las definiciones de rutas.
const routes = new Map();

// English: Adds a new route to the application.
// Español: Añade una nueva ruta a la aplicación.
function addRoute(path, componentName, props = {}) {
    routes.set(path, {
        componentName: componentName,
        props: props
    });
}

// English: Programmatically navigates to a new path.
// Español: Navega programáticamente a una nueva ruta.
function navigateTo(path) {
    if (window.location.hash.substring(1) !== path) {
        window.location.hash = path;
    }
}

// English: Compiles a template from a template element.
// Español: Compila una plantilla a partir de un elemento de plantilla.
function compileTemplate(templateId) {
    let templateElement = document.querySelector(`[data-template="${templateId}"]`);
    if (!templateElement) {
        console.error(`Template element with data-template="${templateId}" not found.`);
        return () => "";
    }

    let templateHTML = templateElement.innerHTML;
    return (context) => templateHTML.replace(/\${([^}]+)}/g, (match, expression) => {
        try {
            return evalInContext(expression.trim(), context);
        } catch (error) {
            return console.error(`Error evaluating template expression: "${expression}"`, error), `Error: ${expression}`;
        }
    });
}

// English: Set up routing and navigation listeners.
// Español: Configura los listeners de enrutamiento y navegación.
window.addEventListener("hashchange", handleRouting);
window.addEventListener("load", handleRouting);
document.addEventListener("click", event => {
    let linkElement = event.target.closest("[data-link]");
    if (linkElement) {
        event.preventDefault();
        let href = linkElement.getAttribute("href");
        if (href) {
            navigateTo(href);
        }
    }
});

// English: Expose the public API on the window object.
// Español: Expone la API pública en el objeto window.
window.App = {
    reactive,
    createComponent,
    addRoute,
    navigateTo,
    mountComponent,
    getComponents: getRegisteredComponents,
    evalInContext
};
