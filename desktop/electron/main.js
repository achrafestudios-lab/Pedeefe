// main.js — cáscara de escritorio de Pedeefe (v1.7).
// Arranca el backend Flask en 127.0.0.1 con puerto efímero y abre una ventana
// sin Node ni navegación externa. No hay auth, TLS ni exposición a red.
'use strict';

const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const READY_LINE = /^PEDEE_READY http:\/\/127\.0\.0\.1:(\d+)\s*$/;
const START_TIMEOUT_MS = 20000;

let backend = null;
let mainWindow = null;
let baseURL = null;
let readyTimer = null;
let shuttingDown = false;

function backendCommand() {
  if (app.isPackaged) {
    const name = process.platform === 'win32' ? 'pedeefe-backend.exe' : 'pedeefe-backend';
    const binary = path.join(process.resourcesPath, 'backend', name);
    return { command: binary, args: [], cwd: path.dirname(binary) };
  }
  const python = process.platform === 'win32'
    ? path.join(__dirname, '..', '..', '.venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '..', '..', '.venv', 'bin', 'python');
  const launcher = path.join(__dirname, '..', 'launcher.py');
  return { command: python, args: [launcher], cwd: path.join(__dirname, '..', '..') };
}

function stopBackend() {
  shuttingDown = true;
  if (readyTimer) clearTimeout(readyTimer);
  if (backend && backend.exitCode === null) {
    backend.kill('SIGTERM');
    const force = setTimeout(() => {
      if (backend && backend.exitCode === null) backend.kill('SIGKILL');
    }, 4000);
    force.unref();
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 820,
    minHeight: 600,
    title: 'Pedeefe',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Solo se permite navegar dentro del propio backend local.
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!baseURL || !url.startsWith(baseURL)) event.preventDefault();
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    return { action: baseURL && url.startsWith(baseURL) ? 'allow' : 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
  mainWindow.loadURL(baseURL);
}

function startBackend() {
  const { command, args, cwd } = backendCommand();
  const uploadDir = path.join(app.getPath('userData'), 'uploads');
  fs.mkdirSync(uploadDir, { recursive: true });

  const env = Object.assign({}, process.env, {
    PEDEE_UPLOAD_FOLDER: uploadDir,
    PEDEE_DESKTOP_PARENT_PID: String(process.pid),
    FLASK_DEBUG: '0',
  });
  delete env.FLASK_HOST;
  delete env.PORT;

  backend = spawn(command, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });

  let buffer = '';
  backend.stdout.on('data', (chunk) => {
    buffer += chunk.toString();
    let end;
    while ((end = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, end).trim();
      buffer = buffer.slice(end + 1);
      const match = READY_LINE.exec(line);
      if (match && !baseURL) {
        baseURL = `http://127.0.0.1:${match[1]}`;
        clearTimeout(readyTimer);
        createWindow();
      }
    }
  });
  backend.stderr.on('data', (chunk) => {
    console.error('[pedeefe-backend]', chunk.toString().trim());
  });
  backend.on('exit', (code, signal) => {
    if (!shuttingDown) {
      shuttingDown = true;
      dialog.showErrorBox(
        'Pedeefe',
        `El backend local se detuvo (código ${code}, señal ${signal || 'ninguna'}).`,
      );
      app.quit();
    }
  });

  readyTimer = setTimeout(() => {
    if (!baseURL) {
      dialog.showErrorBox('Pedeefe', 'El backend local no respondió a tiempo.');
      app.quit();
    }
  }, START_TIMEOUT_MS);
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(startBackend);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0 && baseURL) createWindow();
  });

  app.on('window-all-closed', () => {
    stopBackend();
    app.quit();
  });

  app.on('before-quit', stopBackend);
}
