window.addEventListener('DOMContentLoaded',()=>{
  //  Animations.easeOutBack('div,p,h1,h3,h4,h5,h2,article, i', 300);
})

const Animations = {
    fadeUp: (selector, delay = 0) => {
        return anime({
            targets: selector,
            translateY: [40, 0],
            opacity: [0, 1],
            duration: 800,
            delay: delay,
            easing: 'easeOutQuint'
        });
    },

    fadeIn: (selector, delay = 0) => {
        return anime({
            targets: selector,
            opacity: [0, 1],
            duration: 600,
            delay: delay,
            easing: 'easeInOutQuad'
        });
    },

    staggerFadeUp: (selector) => {
        return anime({
            targets: selector,
            translateY: [30, 0],
            opacity: [0, 1],
            delay: anime.stagger(200, { start: 200 }),
            duration: 700,
            easing: 'easeOutBack'
        });
    },
    easeOutBack: (selector, delay = 300) => {
        anime({
            targets: selector,
            translateY: [15, 0],
            opacity: [0, 1],
            scale: [0.9, 1],
            delay: anime.stagger(80, { start: delay }),
            duration: 600,
            easing: 'easeOutBack'
        });
    }
};
