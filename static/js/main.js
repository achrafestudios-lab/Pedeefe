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

// R-12: indicador de "procesando…" y bloqueo del botón al enviar.
(function () {
    "use strict";

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) ||
            !form.classList.contains("upload-form")) {
            return;
        }
        const input = form.querySelector('input[type="file"]');
        if (!input || input.files.length === 0) {
            return;
        }

        const btn = form.querySelector("button[type=\"submit\"], .btn-primary");
        if (btn && !btn.disabled) {
            btn.disabled = true;
            if (!btn.dataset.originalText) {
                btn.dataset.originalText = btn.textContent;
            }
            btn.textContent = "Procesando…";
        }

        let loading = form.querySelector(".loading-indicator");
        if (!loading) {
            loading = document.createElement("div");
            loading.className = "loading-indicator";
            loading.setAttribute("role", "status");
            loading.setAttribute("aria-live", "polite");
            loading.textContent = "Procesando, por favor espera…";
            form.appendChild(loading);
        }
        loading.hidden = false;
    }, true);
})();

// Navbar por grupos (mega-menú) con accesibilidad.
(function () {
    "use strict";

    function closeAllPanels() {
        document.querySelectorAll(".nav-panel").forEach(function (p) {
            p.hidden = true;
        });
        document.querySelectorAll(".nav-group-toggle").forEach(function (b) {
            b.setAttribute("aria-expanded", "false");
        });
    }

    function closeMobileMenu() {
        const groups = document.getElementById("navGroups");
        const toggle = document.getElementById("navToggle");
        if (groups) groups.classList.remove("open");
        if (toggle) {
            toggle.setAttribute("aria-expanded", "false");
            toggle.textContent = "☰";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const toggle = document.getElementById("navToggle");
        const groups = document.getElementById("navGroups");

        if (toggle && groups) {
            toggle.addEventListener("click", function () {
                const open = groups.classList.toggle("open");
                toggle.setAttribute("aria-expanded", String(open));
                toggle.textContent = open ? "✕" : "☰";
            });
        }

        // Toggles de grupo
        document.querySelectorAll(".nav-group-toggle").forEach(function (btn) {
            btn.addEventListener("click", function (event) {
                event.stopPropagation();
                const panelId = btn.getAttribute("aria-controls");
                const panel = panelId ? document.getElementById(panelId) : null;
                const isOpen = btn.getAttribute("aria-expanded") === "true";

                // Cerrar otros paneles
                document.querySelectorAll(".nav-group-toggle").forEach(function (other) {
                    if (other !== btn) {
                        other.setAttribute("aria-expanded", "false");
                        const otherPanel = document.getElementById(other.getAttribute("aria-controls"));
                        if (otherPanel) otherPanel.hidden = true;
                    }
                });

                if (panel) {
                    if (isOpen) {
                        panel.hidden = true;
                        btn.setAttribute("aria-expanded", "false");
                    } else {
                        panel.hidden = false;
                        btn.setAttribute("aria-expanded", "true");
                    }
                }
            });
        });

        // Cerrar al hacer clic fuera
        document.addEventListener("click", function (event) {
            const target = event.target;
            if (!(target instanceof Element)) {
                return;
            }
            if (!target.closest(".nav-group")) {
                closeAllPanels();
            }
        });

        // Escape cierra paneles y menú móvil
        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }
            const openPanel = document.querySelector(".nav-panel:not([hidden])");
            if (openPanel) {
                closeAllPanels();
                const btn = document.querySelector('.nav-group-toggle[aria-expanded="true"]');
                if (btn) btn.focus();
                return;
            }
            const groupsEl = document.getElementById("navGroups");
            if (groupsEl && groupsEl.classList.contains("open")) {
                closeMobileMenu();
                const t = document.getElementById("navToggle");
                if (t) t.focus();
            }
        });

        // Cerrar menú móvil al navegar
        document.querySelectorAll(".nav-panel a").forEach(function (a) {
            a.addEventListener("click", function () {
                if (window.matchMedia("(max-width: 768px)").matches) {
                    closeMobileMenu();
                    closeAllPanels();
                }
            });
        });
    });
})();
// Drop zone común (R-21): click para abrir selector y drag & drop genérico.
// Sustituye los bloques duplicados que había en las plantillas.
(function () {
    "use strict";

    function initDropZone(zone) {
        const input = zone.querySelector('input[type="file"]');
        if (!input) {
            return;
        }
        zone.addEventListener("click", function () {
            input.click();
        });
        zone.addEventListener("dragover", function (e) {
            e.preventDefault();
            zone.classList.add("dragover");
        });
        zone.addEventListener("dragleave", function () {
            zone.classList.remove("dragover");
        });
        zone.addEventListener("drop", function (e) {
            e.preventDefault();
            zone.classList.remove("dragover");
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            }
        });
    }

    function initAll() {
        document.querySelectorAll(".drop-zone").forEach(initDropZone);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAll);
    } else {
        initAll();
    }
})();

// v1.9: registrar la PWA solo en contextos seguros (localhost/HTTPS) y nunca
// dentro de Electron, donde el backend ya se entrega como aplicación nativa.
(function () {
    "use strict";

    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return;
    }
    if (navigator.userAgent && navigator.userAgent.indexOf("Electron") !== -1) {
        return;
    }

    window.addEventListener("load", function () {
        navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () {
            // La app sigue funcionando sin service worker; no es un error fatal.
        });
    });
})();
