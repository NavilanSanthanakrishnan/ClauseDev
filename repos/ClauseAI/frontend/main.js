const { app, BrowserWindow } = require('electron');
const path = require('path');

let mainWindow;

process.on('uncaughtException', (error) => {
    console.error('[electron-main] Uncaught exception', error);
});

process.on('unhandledRejection', (reason) => {
    console.error('[electron-main] Unhandled rejection', reason);
});

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        webPreferences: {
            nodeIntegration: false,          
            contextIsolation: true,          
            sandbox: true,                  
            webSecurity: true,              
            allowRunningInsecureContent: false,
            preload: path.join(__dirname, 'preload.js')
        }
    });
    
    if (process.env.NODE_ENV === 'development') {
        mainWindow.loadURL('http://localhost:5173');
    } else {
        mainWindow.loadFile(path.join(__dirname, 'dist/index.html'));
    }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});