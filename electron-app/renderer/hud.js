let mediaRecorder;
let audioChunks = [];
let visualizerInterval = null;

const hud = document.getElementById('hud');
const hudText = document.getElementById('hudText');
const bars = document.querySelectorAll('#hudVisualizer .hud-bar');

// --- Visualizer (fake but smooth) ---
function animateBars() {
  bars.forEach(bar => {
    const base = 8;
    const variance = 14;
    const newHeight = base + Math.random() * variance;
    bar.style.height = `${newHeight}px`;
  });
}

function startVisualizer() {
  if (!visualizerInterval) {
    visualizerInterval = setInterval(animateBars, 160);
  }
}

function stopVisualizer() {
  if (visualizerInterval) {
    clearInterval(visualizerInterval);
    visualizerInterval = null;
  }
  // Reset to idle
  bars.forEach((bar, i) => {
    bar.style.height = [12, 18, 10][i] + 'px';
  });
}

// --- Show/Hide HUD based on status ---
function showHUD(text = 'Listening...') {
  hudText.textContent = text;
  hud.classList.add('is-listening');
  startVisualizer();
}

function hideHUD() {
  hud.classList.remove('is-listening');
  stopVisualizer();
}

// --- Electron IPC Handler
window.electronAPI.receive('update-status', async (status) => {
  if (status === 'Listening...') {
    // Reset recording state
    audioChunks = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.onload = () => {
          window.electronAPI.send('audio-data', reader.result);
        };
        reader.readAsArrayBuffer(audioBlob);
      };

      mediaRecorder.start();
      showHUD(status);
    } catch (err) {
      console.error('Mic access failed:', err);
      window.electronAPI.send('mic-error', err.message);
      hideHUD();
    }
  } else {
    // Stop recording and hide HUD
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    hideHUD();
  }
});