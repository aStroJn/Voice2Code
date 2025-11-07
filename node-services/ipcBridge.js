function sendCommand(command) {
  if (process.send) {
    process.send(command);
  }
}

module.exports = { sendCommand };
