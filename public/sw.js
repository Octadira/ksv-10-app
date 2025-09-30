// This is a minimal service worker.
// It is required for the app to be installable (PWA),
// but it does not cache any assets, ensuring the app is always online.

self.addEventListener('install', event => {
  // Skip waiting, activate new service worker immediately
  self.skipWaiting();
});

self.addEventListener('fetch', event => {
  // Do not intercept fetch requests, let them go to the network
  return;
});
