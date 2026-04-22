import { createRoot } from 'react-dom/client';

const componentModules = import.meta.glob('./pages/*.jsx');
const mountedRoots = new Map();

/**
 * Renders or re-renders React components found in the DOM.
 * 
 * @param {string} [name='all'] - The name of the component to render (matching data-react-component). Use "all" to render everything.
 */
window.renderReactComponent = async (name = 'all') => {
  document.querySelectorAll('[data-react-component]').forEach(async (el) => {
    const componentName = el.dataset.reactComponent;
    
    if (name !== 'all' && componentName !== name) return;

    const props = JSON.parse(el.dataset.props || '{}');
    const importer = componentModules[`./pages/${componentName}.jsx`];

    if (importer) {
      try {
        const module = await importer();
        const Component = module.default;

        if (!mountedRoots.has(el)) {
          mountedRoots.set(el, createRoot(el));
        }
        mountedRoots.get(el).render(<Component {...props} key={Math.random()} />);
      } catch (error) {
        console.error(`Failed to render React component: ${componentName}`, error);
      }
    }
  });
};

document.addEventListener('DOMContentLoaded', () => {
  window.renderReactComponent();
});

