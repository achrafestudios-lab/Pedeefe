// preload.js — API mínima y de solo lectura expuesta a la ventana.
'use strict';

const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('pedeefeDesktop', {
  isDesktop: true,
  version: '1.7.0',
});
