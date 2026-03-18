const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('clauseDesktop', {
  platform: process.platform,
});
