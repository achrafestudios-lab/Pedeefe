// sw.js — service worker de Pedeefe (v1.9).
// Guarda solo la cáscara de la aplicación. Nunca intercepta subidas,
// descargas por token ni rutas de procesamiento: el trabajo con PDFs sigue
// necesitando el backend Flask en 127.0.0.1.
"use strict";

const CACHE_NAME = "pedeefe-v2.3.2-ui";
const OFFLINE_URL = "/static/offline.html";
const APP_SHELL = [
    "/",
    "/static/css/style.css",
    "/static/js/main.js",
    "/static/js/productivity.js",
    "/manifest.webmanifest",
    "/static/offline.html",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png",
    "/static/icons/icon-maskable-512.png",
    "/static/brand/pedeefe-logo-horizontal.svg",
    "/static/brand/pedeefe-logo-modo-oscuro.svg",
    "/static/brand/pedeefe-logo-monocromo-horizontal.svg",
    "/static/brand/pedeefe-icono-app.svg",
    "/static/img/background.svg",
    "/static/icons/tools/censurar.svg",
    "/static/icons/tools/comparar.svg",
    "/static/icons/tools/comprimir.svg",
    "/static/icons/tools/comprimir_real.svg",
    "/static/icons/tools/desproteger.svg",
    "/static/icons/tools/dividir.svg",
    "/static/icons/tools/excel_a_pdf.svg",
    "/static/icons/tools/firmar.svg",
    "/static/icons/tools/historial.svg",
    "/static/icons/tools/html_a_pdf.svg",
    "/static/icons/tools/imagen_a_pdf.svg",
    "/static/icons/tools/lotes.svg",
    "/static/icons/tools/marcar_agua.svg",
    "/static/icons/tools/numerar.svg",
    "/static/icons/tools/ocr.svg",
    "/static/icons/tools/pdf_a_excel.svg",
    "/static/icons/tools/pdf_a_html.svg",
    "/static/icons/tools/pdf_a_markdown.svg",
    "/static/icons/tools/pdf_a_imagen.svg",
    "/static/icons/tools/pdf_a_powerpoint.svg",
    "/static/icons/tools/pdf_a_word.svg",
    "/static/icons/tools/plantillas.svg",
    "/static/icons/tools/powerpoint_a_pdf.svg",
    "/static/icons/tools/proteger.svg",
    "/static/icons/tools/recortar_pdf.svg",
    "/static/icons/tools/reordenar_pdf.svg",
    "/static/icons/tools/rotar.svg",
    "/static/icons/tools/unir.svg",
    "/static/icons/tools/word_a_pdf.svg",
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function (cache) { return cache.addAll(APP_SHELL); })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (keys) {
                return Promise.all(
                    keys
                        .filter(function (key) { return key !== CACHE_NAME; })
                        .map(function (key) { return caches.delete(key); })
                );
            })
            .then(function () { return self.clients.claim(); })
    );
});

self.addEventListener("fetch", function (event) {
    const request = event.request;
    let url;
    try {
        url = new URL(request.url);
    } catch (error) {
        return;
    }

    if (
        request.method !== "GET" ||
        url.origin !== self.location.origin ||
        url.pathname === "/sw.js" ||
        url.pathname.startsWith("/descargar_")
    ) {
        return;
    }

    if (request.mode === "navigate") {
        // Red primero: las páginas de herramientas nunca se sirven obsoletas.
        // Si el servidor local no responde, se usa la portada cacheada o la
        // página offline. No se cachean respuestas de navegación.
        event.respondWith(
            fetch(request).catch(async function () {
                const cache = await caches.open(CACHE_NAME);
                return (await cache.match(request)) ||
                    (await cache.match(OFFLINE_URL)) ||
                    Response.error();
            })
        );
        return;
    }

    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(request).then(function (cached) {
                if (cached) {
                    return cached;
                }
                return fetch(request).then(function (response) {
                    if (response.ok) {
                        const copy = response.clone();
                        caches.open(CACHE_NAME).then(function (cache) {
                            cache.put(request, copy);
                        });
                    }
                    return response;
                });
            })
        );
    }
});
