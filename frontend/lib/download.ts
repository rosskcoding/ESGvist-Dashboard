export function triggerFileDownload(path: string) {
  window.location.assign(`${path}${path.includes("?") ? "&" : "?"}download=1&_ts=${Date.now()}`);
}
