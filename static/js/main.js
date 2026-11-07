// main.js — JavaScript global del proyecto.
// Comportamiento compartido de la zona de arrastre (R-03) y validación vacía (R-04).
(function () {
    "use strict";

    function showError(form) {
        const error = form.querySelector("#fileError");
        if (error) {
            error.hidden = false;
        }
    }

    function hideError(form) {
        const error = form.querySelector("#fileError");
        if (error) {
            error.hidden = true;
        }
    }

    // R-03: la drop zone es focusable (role="button", tabindex="0") y se activa
    // con Enter o Espacio, abriendo el selector de archivos.
    document.addEventListener("keydown", function (event) {
        const zone = event.target && event.target.closest
            ? event.target.closest(".drop-zone")
            : null;
        if (!zone) {
            return;
        }
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }
        const input = zone.querySelector('input[type="file"]');
        if (!input) {
            return;
        }
        event.preventDefault();
        input.click();
    });

    // Ocultar el aviso cuando el usuario selecciona un archivo.
    document.addEventListener("change", function (event) {
        const input = event.target;
        if (!(input instanceof HTMLInputElement) || input.type !== "file") {
            return;
        }
        const form = input.closest("form");
        if (form) {
            hideError(form);
        }
    });

    // R-04: evitar el envío silencioso sin archivo y mostrar un mensaje visible.
    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) ||
            !form.classList.contains("upload-form")) {
            return;
        }
        const input = form.querySelector('input[type="file"]');
        const zone = form.querySelector(".drop-zone");
        if (input && input.files.length === 0) {
            event.preventDefault();
            showError(form);
            if (zone) {
                zone.focus();
            }
        } else {
            hideError(form);
        }
    }, true);
})();

// R-11: menú desplegable de la navbar (hamburguesa) con accesibilidad.
(function () {
    "use strict";

    function closeMenu() {
        const links = document.getElementById("navLinks");
        const toggle = document.getElementById("navToggle");
        if (!links || !toggle) {
            return;
        }
        links.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.textContent = "☰";
    }

    document.addEventListener("DOMContentLoaded", function () {
        const toggle = document.getElementById("navToggle");
        const links = document.getElementById("navLinks");
        if (!toggle || !links) {
            return;
        }

        toggle.addEventListener("click", function () {
            const open = links.classList.toggle("open");
            toggle.setAttribute("aria-expanded", String(open));
            toggle.textContent = open ? "✕" : "☰";
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && links.classList.contains("open")) {
                closeMenu();
                toggle.focus();
            }
        });

        links.querySelectorAll("a").forEach(function (a) {
            a.addEventListener("click", function () {
                if (window.matchMedia("(max-width: 768px)").matches) {
                    closeMenu();
                }
            });
        });
    });
})();