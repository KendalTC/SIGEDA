'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Lo que la pantalla de carga (renderer/loading.html) puede escuchar y
// pedir. La app web (Next) no usa nada de esto.
contextBridge.exposeInMainWorld('sigeda', {
  // Paso actual ("Iniciando servicios...").
  onStatus: (callback) => {
    ipcRenderer.on('sigeda:status', (_event, text) => callback(text));
  },
  // Punto 7: cada línea de salida, para el historial en pantalla.
  onLog: (callback) => {
    ipcRenderer.on('sigeda:log', (_event, line) => callback(line));
  },
  // Qué acción corre y cuánto puede tardar: { title, hint }.
  onPhase: (callback) => {
    ipcRenderer.on('sigeda:phase', (_event, phase) => callback(phase));
  },
  // La acción falló: { title, reasons, exitCode, logPath }.
  onFailed: (callback) => {
    ipcRenderer.on('sigeda:failed', (_event, failure) => callback(failure));
  },
  // Botón "Reintentar" de la pantalla de error: vuelve a levantar SIGEDA.
  retry: () => {
    ipcRenderer.send('sigeda:retry');
  },
});
