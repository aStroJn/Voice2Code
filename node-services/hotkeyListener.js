const { GlobalKeyboardListener } = require('node-global-key-listener');
const fs = require('fs');
const path = require('path');
const { sendCommand } = require('./ipcBridge');

const SETTINGS_PATH = path.join(__dirname, '../config/settings.json');

function loadSettings() {
    try {
        const settingsContent = fs.readFileSync(SETTINGS_PATH, 'utf8');
        return JSON.parse(settingsContent);
    } catch (error) {
        console.error('Error loading settings.json:', error);
        return {};
    }
}

const settings = loadSettings();
const configuredHotkey = settings.hotkey || 'NUMPAD 5'; // Default to NUMPAD 5 if not found

const hotkeyParts = configuredHotkey.toLowerCase().split(' + ').map(part => part.trim());
let modifierKey = null;
let mainKey = null;

const modifierMap = {
    'alt': 'LEFT ALT',
    'control': 'LEFT CONTROL',
    'shift': 'LEFT SHIFT',
    'commandorcontrol': process.platform === 'darwin' ? 'LEFT COMMAND' : 'LEFT CONTROL'
};

if (hotkeyParts.length > 1) {
    modifierKey = modifierMap[hotkeyParts[0]];
    mainKey = hotkeyParts[1].toUpperCase();
} else {
    mainKey = hotkeyParts[0].toUpperCase();
}

let isModifierDown = false;
let hotkeyActive = false;

const v = new GlobalKeyboardListener();

v.addListener(function (e) {
    const isKeyDown = (e.state === 'DOWN');

    if (modifierKey) {
        if (e.name === modifierKey) {
            isModifierDown = isKeyDown;
            if (!isKeyDown && hotkeyActive) { // Modifier released, hotkey was active
                sendCommand({ command: 'hide-hud' });
                hotkeyActive = false;
            }
        }

        if (e.name === mainKey) {
            if (isKeyDown && isModifierDown && !hotkeyActive) {
                sendCommand({ command: 'show-hud' });
                hotkeyActive = true;
            } else if (!isKeyDown && hotkeyActive) {
                sendCommand({ command: 'hide-hud' });
                hotkeyActive = false;
            }
        }
    } else if (e.name === mainKey) {
        if (isKeyDown && !hotkeyActive) {
            sendCommand({ command: 'show-hud' });
            hotkeyActive = true;
        } else if (!isKeyDown && hotkeyActive) {
            sendCommand({ command: 'hide-hud' });
            hotkeyActive = false;
        }
    }
});

