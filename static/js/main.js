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