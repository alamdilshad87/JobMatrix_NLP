(function () {
    // Hairline under the nav once the page scrolls
    var header = document.getElementById('site-header');
    function onScroll() { if (header) header.classList.toggle('scrolled', window.scrollY > 8); }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // Mobile menu
    var toggle = document.getElementById('nav-toggle');
    var links = document.getElementById('nav-links');
    if (toggle && links) {
        toggle.addEventListener('click', function () {
            var open = links.classList.toggle('open');
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            toggle.textContent = open ? 'Close' : 'Menu';
        });
    }

    // Reveal on scroll; fill bars when they come into view
    function activate(el) {
        el.classList.add('in');
        el.querySelectorAll('.bar > span[data-w]').forEach(function (b) {
            b.style.setProperty('--w', Math.min(parseFloat(b.getAttribute('data-w')), 100) + '%');
        });
    }
    var targets = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) { if (e.isIntersecting) { activate(e.target); io.unobserve(e.target); } });
        }, { rootMargin: '0px 0px -40px 0px' });
        targets.forEach(function (el) { io.observe(el); });
    } else {
        targets.forEach(activate);
    }
})();
