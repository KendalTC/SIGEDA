'use strict';

// Envoltorio delgado sobre wsl.exe. No reimplementa nada de la lógica de
// negocio: solo invoca, sin modificar, los scripts que ya existen en
// scripts/*.sh dentro de la distro "sigeda-wsl". La restauración real del
// archivo documental (RF-16) NO es un script: es una funcionalidad de la
// propia aplicación web de SIGEDA (PAN-08/D-05, apps/respaldos), detrás de
// sesión iniciada, confirmación escrita y, según el plan vigente, solo
// disponible para la cuenta Administración -- por eso no hace falta
// exponerla aquí. rollback.sh (revertir una actualización de código
// fallida, no un respaldo del archivo) sigue sin exponerse a propósito --
// es un procedimiento distinto y peligroso, manual por WSL con
// confirmación escrita. update.sh sí se expone (ver
// updateApplication más abajo), porque es la única vía real para llevar
// cambios de Django/Next a una instalación que ya existe: reinstalar el
// .exe NO alcanza, install-wsl-distro.ps1 se salta la reimportación del
// .tar si la distro ya existe (para no perder datos), así que la imagen
// dorada nunca llega a una máquina que ya tiene SIGEDA instalado. La
// confirmación con el usuario vive en main.js, antes de llamar a esta
// función.

const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const DISTRO = 'sigeda-wsl';
const APP_ROOT = '/opt/sigeda';
const HEALTH_URL = 'http://127.0.0.1/nginx-health';
const START_TIMEOUT_MS = 3 * 60 * 1000;
const POLL_INTERVAL_MS = 2000;

// En un build empaquetado, extraResources ("resources/windows" en
// package.json) queda bajo process.resourcesPath/windows. En desarrollo
// (electron .), process.resourcesPath apunta a los recursos propios de
// Electron, no a los nuestros -- ahí hay que leer directo de la carpeta del
// repo.
const RESOURCES_WINDOWS_DIR = app.isPackaged
  ? path.join(process.resourcesPath, 'windows')
  : path.join(__dirname, '..', 'resources', 'windows');

// Los scripts marcan sus errores con "[ERROR] ..." (log_error en
// scripts/lib/common.sh). Esas líneas son el motivo real de una falla;
// el resto de la salida (docker compose, etc.) es contexto.
const ERROR_LINE_PATTERN = /^\s*\[ERROR\]\s*/;
const ANSI_PATTERN = /\x1b\[[0-9;]*m/g;
const OUTPUT_TAIL_LINES = 40;

function cleanLine(line) {
  return line.replace(ANSI_PATTERN, '').trimEnd();
}

function spawnInDistro(args, { onLine, stdin } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn('wsl.exe', ['-d', DISTRO, '--', ...args], {
      windowsHide: true,
    });

    // stdout y stderr juntos, en el orden en que llegan: los scripts
    // escriben [INFO]/[OK] por stdout y [ERROR] por stderr, y para
    // entender una falla hace falta ver los dos.
    const outputTail = [];
    const errorLines = [];

    const handleChunk = (chunk) => {
      chunk
        .toString('utf8')
        .split(/\r?\n/)
        .map(cleanLine)
        .filter(Boolean)
        .forEach((line) => {
          outputTail.push(line);
          if (outputTail.length > OUTPUT_TAIL_LINES) {
            outputTail.shift();
          }

          if (ERROR_LINE_PATTERN.test(line)) {
            errorLines.push(line.replace(ERROR_LINE_PATTERN, ''));
          }

          if (onLine) {
            onLine(line);
          }
        });
    };

    child.stdout.on('data', handleChunk);
    child.stderr.on('data', handleChunk);

    child.on('error', (err) => {
      reject(new Error(`No se pudo invocar wsl.exe: ${err.message}`));
    });

    child.on('close', (code) => {
      if (code === 0) {
        resolve();
        return;
      }

      // El mensaje lleva primero el motivo ([ERROR]); si el script no
      // dejó ninguno, las últimas líneas de la salida.
      const reason = errorLines.length
        ? errorLines.join('\n')
        : outputTail.slice(-15).join('\n') || 'sin detalle';

      const error = new Error(`Falló dentro de WSL (código ${code}):\n${reason}`);
      error.exitCode = code;
      error.errorLines = errorLines;
      error.outputTail = outputTail.slice();
      reject(error);
    });

    if (stdin !== undefined) {
      child.stdin.write(stdin);
      child.stdin.end();
    }
  });
}

function runInDistro(command, onLine) {
  return spawnInDistro(['bash', '-lc', command], { onLine });
}

function runScriptFileInDistro(scriptFileName, onLine) {
  const scriptPath = path.join(RESOURCES_WINDOWS_DIR, scriptFileName);
  let scriptContent;

  try {
    scriptContent = fs.readFileSync(scriptPath, 'utf8');
  } catch (err) {
    return Promise.reject(new Error(`No se pudo leer ${scriptFileName}: ${err.message}`));
  }

  // Se manda por stdin a "bash -l -s" en vez de copiar el archivo dentro de
  // la distro primero: evita depender de que exista un directorio temporal
  // escribible y evita problemas de permisos/CRLF al cruzar la frontera
  // Windows -> WSL con un archivo intermedio. "-l" (login shell) para que
  // tenga el mismo PATH que el resto de las invocaciones de este archivo
  // ("bash -lc ..." en runInDistro), no el PATH mínimo de un shell no-login.
  return spawnInDistro(['bash', '-l', '-s'], { onLine, stdin: scriptContent });
}

async function ensureDistroRunning() {
  // Cualquier comando "wsl -d sigeda-wsl" arranca la distro si estaba apagada,
  // así que esto alcanza como comprobación mínima de que WSL2 responde.
  await runInDistro('true');
}

function startServices(onLine) {
  return runInDistro(`${APP_ROOT}/scripts/start.sh`, onLine);
}

function restartServices(onLine) {
  return runInDistro(`${APP_ROOT}/scripts/restart.sh`, onLine);
}

function stopServices(onLine) {
  return runInDistro(`${APP_ROOT}/scripts/stop.sh`, onLine);
}

function getStatus(onLine) {
  return runInDistro(`${APP_ROOT}/scripts/status.sh`, onLine);
}

function runHealthcheck(onLine) {
  return runInDistro(`${APP_ROOT}/scripts/healthcheck.sh`, onLine);
}

function backupNow(onLine) {
  // RF-16/ADR-03: respaldo real (base + almacén de documentos, cifrado
  // AES-256-GCM, verificado con SHA-256), apps/respaldos del Incremento
  // 3a -- no el scripts/backup.sh viejo (retirado, solo hacía pg_dump
  // de la base, sin documentos y sin cifrar).
  return runInDistro(
    `docker compose -f ${APP_ROOT}/infra/docker/compose.prod.yml exec -T backend python src/manage.py respaldar manual`,
    onLine,
  );
}

function updateApplication(onLine) {
  // Actualiza Django + Next a la versión nueva dentro de una instalación
  // YA existente, sin tocar la imagen dorada ni el .exe. Requiere que el
  // release offline nuevo (mismo formato que build-offline-release.sh)
  // ya esté copiado a mano en C:\sigeda-dev\ en esta máquina Windows -- ver
  // el comentario largo en resources/windows/update-application.sh y la
  // sección "Actualizar la aplicación" de infra/windows/README.md.
  return runScriptFileInDistro('update-application.sh', onLine);
}

function waitHealthy(timeoutMs = START_TIMEOUT_MS) {
  const start = Date.now();

  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(HEALTH_URL, { timeout: 5000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
      });

      req.on('error', retry);
      req.on('timeout', () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start >= timeoutMs) {
        reject(new Error('SIGEDA no respondió a tiempo en ' + HEALTH_URL));
        return;
      }
      setTimeout(attempt, POLL_INTERVAL_MS);
    };

    attempt();
  });
}

module.exports = {
  ensureDistroRunning,
  startServices,
  restartServices,
  stopServices,
  getStatus,
  runHealthcheck,
  backupNow,
  updateApplication,
  waitHealthy,
};
