const { app, BrowserWindow } = require('electron');
const path = require('node:path');

const isDev = !app.isPackaged;

function createWindow() {
  const window = new BrowserWindow({
    width: 1560,
    height: 980,
    minWidth: 1200,
    minHeight: 760,
    backgroundColor: '#090909',
    title: 'Clause',
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    window.loadURL(process.env.ELECTRON_RENDERER_URL || 'http://127.0.0.1:5173');
    window.webContents.openDevTools({ mode: 'detach' });
    return;
  }

  window.loadFile(path.join(__dirname, '../../frontend/dist/index.html'));
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

