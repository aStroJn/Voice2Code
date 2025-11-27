const { app, BrowserWindow, ipcMain, Tray, Menu, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

let tray = null;
let mainWindow = null;
let hudWindow = null;
let settingsWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 480,
    height: 500,
    frame: false,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false
    }
  });

  mainWindow.loadFile('renderer/index.html');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'assets/icons/icon.png')); // Ensure you have an icon file here
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Settings', type: 'normal', click: () => {
        if (settingsWindow) {
          settingsWindow.focus();
        } else {
          createSettingsWindow();
        }
      }
    },
    { label: 'Quit', type: 'normal', click: () => app.quit() }
  ]);
  tray.setToolTip('Voice2Code');
  tray.setContextMenu(contextMenu);
}

function createHudWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth } = primaryDisplay.workAreaSize;
  const hudWidth = 300;
  const hudHeight = 150;

  hudWindow = new BrowserWindow({
    width: hudWidth,
    height: hudHeight,
    x: screenWidth - hudWidth - 1,
    y: 1,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false
    }
  });

  hudWindow.loadFile('renderer/hud.html');
  hudWindow.hide();
}

function createSettingsWindow() {
  settingsWindow = new BrowserWindow({
    width: 500,
    height: 400,
    title: 'Settings',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false
    }
  });

  settingsWindow.loadFile('renderer/settings.html');
  settingsWindow.setMenu(null); // Optional: removes the default menu

  settingsWindow.on('closed', () => {
    settingsWindow = null;
  });
}

function showHud() {
  hudWindow.show();
  hudWindow.webContents.send('update-status', 'Listening...');
}

function hideHud() {
  hudWindow.hide();
  hudWindow.webContents.send('update-status', 'Stopped');
}

ipcMain.on('close-loading-window', () => {
  if (mainWindow) {
    mainWindow.close();
  }
});

app.on('ready', () => {
  createWindow();
  createTray();
  createHudWindow();

  const hotkeyListener = spawn('node', [path.join(__dirname, '../node-services/hotkeyListener.js')], { stdio: ['pipe', 'pipe', 'pipe', 'ipc'] });

  hotkeyListener.stdout.on('data', (data) => {
    console.log(`hotkeyListener stdout: ${data}`);
  });

  hotkeyListener.stderr.on('data', (data) => {
    console.error(`hotkeyListener stderr: ${data}`);
  });

  hotkeyListener.on('message', (message) => {
    if (message.command === 'show-hud') {
      showHud();
    } else if (message.command === 'hide-hud') {
      hideHud();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

ipcMain.on('toMain', (event, args) => {
  console.log(args);
});

ipcMain.on('audio-data', (event, data) => {
  const tempPathUnconverted = path.join(os.tmpdir(), 'temp_audio_unconverted.wav');
  const tempPathConverted = path.join(os.tmpdir(), 'temp_audio_converted.wav');
  const ffmpegPath = path.join(__dirname, '../backend/models/ffmpeg/ffmpeg.exe');

  fs.writeFile(tempPathUnconverted, Buffer.from(data), (err) => {
    if (err) {
      console.error('Failed to save unconverted audio file:', err);
      return;
    }
    console.log('Unconverted audio file saved to:', tempPathUnconverted);

    try {
      const stats = fs.statSync(tempPathUnconverted);
      console.log(`Unconverted audio file size: ${stats.size} bytes`);
      if (stats.size === 0) {
        console.error('Error: Unconverted audio file is empty. Aborting conversion.');
        return;
      }
    } catch (e) {
      console.error('Error getting file stats:', e);
      return;
    }

    // Command to convert the audio file using ffmpeg
    // -i: input file
    // -ar 16000: set audio sample rate to 16kHz
    // -ac 1: set number of audio channels to 1 (mono)
    // -c:a pcm_s16le: set audio codec to 16-bit signed little-endian PCM
    // -y: overwrite output file if it exists
    const ffmpegCommand = [
      ffmpegPath,
      '-i', tempPathUnconverted,
      '-ar', '16000',
      '-ac', '1',
      '-c:a', 'pcm_s16le',
      '-y', tempPathConverted
    ];

    console.log('Running ffmpeg command:', ffmpegCommand.join(' '));

    const ffmpegProcess = spawn(ffmpegPath, [
      '-i', tempPathUnconverted,
      '-ar', '16000',
      '-ac', '1',
      '-c:a', 'pcm_s16le',
      '-y', tempPathConverted
    ]);

    let ffmpegStderr = '';
    ffmpegProcess.stderr.on('data', (data) => {
      ffmpegStderr += data.toString();
    });

    ffmpegProcess.on('close', (code) => {
      if (code !== 0) {
        console.error(`ffmpeg process exited with code ${code}`);
        return;
      }
      console.log('Converted audio file saved to:', tempPathConverted);

      // Now send the CONVERTED file to the backend
      const axios = require('axios');
      axios.post('http://127.0.0.1:5001/process-audio', { path: tempPathConverted })
        .then(response => {
          const code = response.data.code;
          const automation = spawn('node', [path.join(__dirname, '../node-services/automation.js'), code], { stdio: ['pipe', 'pipe', 'pipe', 'ipc'] });

          automation.stdout.on('data', (data) => {
            console.log(`automation.js stdout: ${data}`);
          });

          automation.stderr.on('data', (data) => {
            console.error(`automation.js stderr: ${data}`);
          });

          automation.on('message', (message) => {
            console.log(`automation.js message: ${JSON.stringify(message)}`);
          });

          automation.on('close', (code) => {
            console.log(`automation.js exited with code ${code}`);
          });
        })
        .catch(error => {
          console.error('Error processing audio:', error);

          // Show user-friendly error dialog
          const { dialog } = require('electron');

          let errorMessage = 'An error occurred while processing your voice command.';

          // Check if it's a no_audio error (blank transcription)
          if (error.response && error.response.data) {
            if (error.response.data.error_type === 'no_audio') {
              errorMessage = 'No audio was recorded. Please try speaking again.';
            } else if (error.response.data.error) {
              errorMessage = error.response.data.error;
            }
          }

          dialog.showMessageBox({
            type: 'error',
            title: 'Voice2Code Error',
            message: errorMessage,
            buttons: ['OK']
          });
        });
    });
  });
});
