const { clipboard } = require("@nut-tree-fork/nut-js");

async function copyToClipboard(text) {
    await clipboard.setContent(text);
}

const codeToCopy = process.argv[2];
if (codeToCopy) {
    copyToClipboard(codeToCopy).then(() => {
        if (process.send) {
            process.send({ status: 'success' });
        }
    });
}
