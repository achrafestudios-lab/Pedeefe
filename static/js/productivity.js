// productivity.js — v1.5: historial y plantillas locales (localStorage).
// Reglas de privacidad: solo metadatos y parámetros. Nunca archivos, contenido
// de PDFs ni contraseñas. Los datos caducan y se limitan por página.
(function () {
    "use strict";

    var HISTORY_KEY = "pedeefe.history.v1";
    var TEMPLATE_KEY = "pedeefe.templates.v1";
    var DAY_MS = 24 * 60 * 60 * 1000;
    var DEFAULT_HISTORY_TTL = 30;
    var DEFAULT_HISTORY_MAX = 50;
    var DEFAULT_TEMPLATE_TTL = 90;
    var DEFAULT_TEMPLATE_MAX = 20;

    var TOOL_NAMES = {
        "/unir": "Unir PDFs",
        "/dividir": "Dividir PDF",
        "/recortar-pdf": "Recortar PDF",
        "/reordenar-pdf": "Reordenar PDF",
        "/comprimir": "Optimizar PDF",
        "/comprimir-real": "Comprimir PDF",
        "/pdf-a-imagen": "PDF a Imagen",
        "/imagen-a-pdf": "Imágenes a PDF",
        "/pdf-a-word": "PDF a Word",
        "/pdf-a-excel": "PDF a Excel",
        "/pdf-a-powerpoint": "PDF a PowerPoint",
        "/pdf-a-html": "PDF a HTML",
        "/word-a-pdf": "Word a PDF",
        "/excel-a-pdf": "Excel a PDF",
        "/powerpoint-a-pdf": "PowerPoint a PDF",
        "/html-a-pdf": "HTML a PDF",
        "/rotar": "Rotar PDF",
        "/proteger": "Proteger PDF",
        "/desproteger": "Desproteger PDF",
        "/ocr": "OCR de PDF",
        "/marcar-agua": "Marca de agua",
        "/numerar": "Numerar páginas",
        "/firmar": "Firmar PDF",
        "/censurar": "Censurar PDF",
        "/comparar": "Comparar PDF",
        "/lotes": "Lotes PDF"
    };

    // ─── Almacenamiento ────────────────────────────────────────────

    function read(key) {
        try {
            var raw = window.localStorage.getItem(key);
            if (!raw) {
                return [];
            }
            var parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    }

    function write(key, items) {
        try {
            window.localStorage.setItem(key, JSON.stringify(items));
            return true;
        } catch (error) {
            return false;
        }
    }

    function prune(items, ttlDays, limit) {
        var now = Date.now();
        return items.filter(function (item) {
            return item && typeof item === "object" &&
                typeof item.created === "number" &&
                now - item.created < ttlDays * DAY_MS;
        }).slice(0, limit);
    }

    function load(key, ttlDays, limit) {
        var items = prune(read(key), ttlDays, limit);
        write(key, items);
        return items;
    }

    function newId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }
        return "id-" + Date.now() + "-" + Math.random().toString(36).slice(2);
    }

    // ─── Formularios ───────────────────────────────────────────────

    function toolName(form, path) {
        if (form.getAttribute("data-tool")) {
            return form.getAttribute("data-tool");
        }
        return TOOL_NAMES[path] || path.replace(/^\//, "") || "Herramienta";
    }

    function formParams(form) {
        var params = {};
        Array.prototype.forEach.call(form.elements, function (field) {
            if (!field.name || field.disabled) {
                return;
            }
            if (field.type === "file" || field.type === "password" ||
                field.type === "submit" || field.type === "button" ||
                field.name.toLowerCase().indexOf("password") !== -1) {
                return;
            }
            if (field.type === "radio" || field.type === "checkbox") {
                if (field.checked) {
                    params[field.name] = field.value;
                }
                return;
            }
            if (field.type === "textarea" || field.type === "select-one" ||
                field.type === "select-multiple" || field.type === "text" ||
                field.type === "number" || field.type === "search") {
                params[field.name] = field.value;
            }
        });
        return params;
    }

    function applyQueryParams() {
        var query = new URLSearchParams(window.location.search);
        if (!Array.from(query.keys()).length) {
            return;
        }
        document.querySelectorAll("form.upload-form").forEach(function (form) {
            query.forEach(function (value, key) {
                var field = form.elements[key];
                if (!field || field.type === "file" || field.type === "password") {
                    return;
                }
                if (typeof field.length === "number" && !field.nodeType) {
                    Array.prototype.forEach.call(field, function (option) {
                        option.checked = option.value === value;
                    });
                } else {
                    field.value = value;
                }
                field.dispatchEvent(new Event("change", { bubbles: true }));
            });
        });
    }

    function recordSubmission() {
        document.addEventListener("submit", function (event) {
            var form = event.target;
            if (!(form instanceof HTMLFormElement) ||
                !form.classList.contains("upload-form") ||
                event.defaultPrevented) {
                return;
            }
            var input = form.querySelector('input[type="file"]');
            if (!input || !input.files.length) {
                return;
            }
            var path = window.location.pathname;
            var files = Array.prototype.map.call(input.files, function (file) {
                return file.name;
            });
            var items = load(HISTORY_KEY, DEFAULT_HISTORY_TTL, DEFAULT_HISTORY_MAX);
            items.unshift({
                id: newId(),
                tool: toolName(form, path),
                path: path,
                files: files,
                params: formParams(form),
                created: Date.now()
            });
            write(HISTORY_KEY, items.slice(0, DEFAULT_HISTORY_MAX));
        });
    }

    // ─── Renderizado con textContent (sin inyección de HTML) ───────

    function element(tag, className, text) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined && text !== null) {
            node.textContent = String(text);
        }
        return node;
    }

    function clear(node) {
        while (node.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function summary(params) {
        var keys = params && typeof params === "object" ? Object.keys(params) : [];
        if (!keys.length) {
            return "Sin opciones adicionales";
        }
        return keys.map(function (key) {
            return key + ": " + params[key];
        }).join(" · ");
    }

    function safePath(path) {
        return typeof path === "string" && path.indexOf("/") === 0 &&
            path.indexOf("//") !== 0 ? path : "";
    }

    function makeLink(item, label) {
        var path = safePath(item.path);
        if (!path) {
            return null;
        }
        var link = element("a", "btn btn-secondary btn-small", label);
        link.href = path + "?" + new URLSearchParams(item.params || {}).toString();
        return link;
    }

    function itemCard(item, options) {
        var card = element("article", "productivity-item");
        var heading = element("h3", "", options.title || item.tool);
        card.appendChild(heading);
        card.appendChild(element("p", "productivity-meta",
            new Date(item.created).toLocaleString("es-ES")));
        if (options.files && item.files && item.files.length) {
            card.appendChild(element("p", "", "Archivos: " + item.files.join(", ")));
        }
        card.appendChild(element("p", "productivity-params", summary(item.params)));

        var actions = element("div", "productivity-actions");
        var link = makeLink(item, options.linkLabel);
        if (link) {
            actions.appendChild(link);
        }
        var remove = element("button", "btn btn-secondary btn-small", "Eliminar");
        remove.type = "button";
        remove.setAttribute("data-remove-id", item.id);
        remove.setAttribute("data-remove-key", options.key);
        actions.appendChild(remove);
        card.appendChild(actions);
        return card;
    }

    function renderHistory() {
        var container = document.getElementById("history-list");
        if (!container) {
            return;
        }
        var ttl = Number(container.getAttribute("data-ttl-days")) || DEFAULT_HISTORY_TTL;
        var max = Number(container.getAttribute("data-max")) || DEFAULT_HISTORY_MAX;
        var search = document.getElementById("history-search");
        var query = search ? search.value.trim().toLowerCase() : "";
        var items = load(HISTORY_KEY, ttl, max).filter(function (item) {
            if (!query) {
                return true;
            }
            var text = (item.tool || "") + " " + (item.files || []).join(" ");
            return text.toLowerCase().indexOf(query) !== -1;
        });

        clear(container);
        if (!items.length) {
            container.appendChild(element("p", "empty-state",
                query ? "No hay entradas que coincidan con la búsqueda." :
                    "Todavía no hay operaciones guardadas en este navegador."));
            return;
        }
        items.forEach(function (item) {
            container.appendChild(itemCard(item, {
                key: HISTORY_KEY,
                title: item.tool,
                files: true,
                linkLabel: "Reutilizar opciones"
            }));
        });
    }

    function renderTemplates() {
        var container = document.getElementById("template-list");
        if (!container) {
            return;
        }
        var ttl = Number(container.getAttribute("data-ttl-days")) || DEFAULT_TEMPLATE_TTL;
        var max = Number(container.getAttribute("data-max")) || DEFAULT_TEMPLATE_MAX;
        var items = load(TEMPLATE_KEY, ttl, max);

        clear(container);
        if (!items.length) {
            container.appendChild(element("p", "empty-state",
                "No hay plantillas guardadas. Usa «Guardar como plantilla» en cualquier herramienta."));
            return;
        }
        items.forEach(function (item) {
            container.appendChild(itemCard(item, {
                key: TEMPLATE_KEY,
                title: item.name + " · " + item.tool,
                files: false,
                linkLabel: "Usar plantilla"
            }));
        });
    }

    // ─── Botones de plantilla en los formularios ───────────────────

    function addTemplateButtons() {
        document.querySelectorAll("form.upload-form").forEach(function (form) {
            if (form.querySelector(".template-save")) {
                return;
            }
            var submit = form.querySelector('button[type="submit"]');
            if (!submit || !submit.parentNode) {
                return;
            }

            var wrapper = element("div", "template-save");
            var toggle = element("button", "btn btn-secondary btn-small",
                "💾 Guardar como plantilla");
            toggle.type = "button";
            var panel = element("div", "template-save-panel");
            panel.hidden = true;

            var label = element("label", "", "Nombre de la plantilla");
            var input = document.createElement("input");
            input.type = "text";
            input.maxLength = 60;
            input.placeholder = "Ej.: Rotación 90 para informes";
            label.appendChild(input);

            var save = element("button", "btn btn-primary btn-small", "Guardar");
            save.type = "button";
            var cancel = element("button", "btn btn-secondary btn-small", "Cancelar");
            cancel.type = "button";
            var status = element("p", "template-save-status");
            status.setAttribute("role", "status");

            panel.appendChild(label);
            panel.appendChild(save);
            panel.appendChild(cancel);
            panel.appendChild(status);
            wrapper.appendChild(toggle);
            wrapper.appendChild(panel);
            submit.parentNode.insertBefore(wrapper, submit.nextSibling);

            toggle.addEventListener("click", function () {
                panel.hidden = !panel.hidden;
                if (!panel.hidden) {
                    input.focus();
                }
            });
            cancel.addEventListener("click", function () {
                panel.hidden = true;
                toggle.focus();
            });
            save.addEventListener("click", function () {
                var name = input.value.trim();
                if (!name) {
                    status.textContent = "Escribe un nombre para la plantilla.";
                    input.focus();
                    return;
                }
                var items = load(TEMPLATE_KEY, DEFAULT_TEMPLATE_TTL, DEFAULT_TEMPLATE_MAX);
                items.unshift({
                    id: newId(),
                    name: name.slice(0, 60),
                    tool: toolName(form, window.location.pathname),
                    path: window.location.pathname,
                    params: formParams(form),
                    created: Date.now()
                });
                var saved = write(TEMPLATE_KEY, items.slice(0, DEFAULT_TEMPLATE_MAX));
                status.textContent = saved
                    ? "Plantilla guardada en este navegador."
                    : "No se pudo guardar. Revisa el almacenamiento del navegador.";
                if (saved) {
                    input.value = "";
                    panel.hidden = true;
                    toggle.focus();
                }
            });
        });
    }

    function wireLists() {
        document.addEventListener("click", function (event) {
            var button = event.target && event.target.closest
                ? event.target.closest("[data-remove-id]") : null;
            if (!button) {
                return;
            }
            var key = button.getAttribute("data-remove-key") === TEMPLATE_KEY
                ? TEMPLATE_KEY : HISTORY_KEY;
            var remaining = read(key).filter(function (item) {
                return item.id !== button.getAttribute("data-remove-id");
            });
            write(key, remaining);
            renderHistory();
            renderTemplates();
        });

        var clearHistory = document.getElementById("history-clear");
        if (clearHistory) {
            clearHistory.addEventListener("click", function () {
                if (window.confirm("¿Borrar todo el historial guardado en este navegador?")) {
                    write(HISTORY_KEY, []);
                    renderHistory();
                }
            });
        }
        var clearTemplates = document.getElementById("templates-clear");
        if (clearTemplates) {
            clearTemplates.addEventListener("click", function () {
                if (window.confirm("¿Borrar todas las plantillas guardadas en este navegador?")) {
                    write(TEMPLATE_KEY, []);
                    renderTemplates();
                }
            });
        }
        var search = document.getElementById("history-search");
        if (search) {
            search.addEventListener("input", renderHistory);
        }
    }

    function init() {
        applyQueryParams();
        addTemplateButtons();
        recordSubmission();
        renderHistory();
        renderTemplates();
        wireLists();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    // Superficie pública para depuración y comprobaciones manuales.
    window.PedeefeProductivity = {
        keys: { history: HISTORY_KEY, templates: TEMPLATE_KEY },
        read: read,
        write: write,
        prune: prune,
        formParams: formParams,
        toolName: toolName
    };
})();
