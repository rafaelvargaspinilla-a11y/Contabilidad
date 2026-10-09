export const browserMode = Boolean(globalThis.misCuentasBrowser);

export async function downloadFile(path) {
  if (!browserMode) {
    window.location.assign(path);
    return;
  }
  const file = await globalThis.misCuentasBrowser.request(path);
  const url = URL.createObjectURL(new Blob([file.bytes], {type: file.mime}));
  const link = document.createElement('a');
  link.href = url;
  link.download = file.filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
