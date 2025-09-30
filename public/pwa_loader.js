window.addEventListener('load', () => {
  // 1. Add the manifest link to the head
  const manifestLink = document.createElement('link');
  manifestLink.rel = 'manifest';
  manifestLink.href = '/public/manifest.json';
  document.head.appendChild(manifestLink);

  // 2. Register the service worker
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/public/sw.js')
      .then(registration => {
        console.log('Service Worker registered with scope:', registration.scope);
      })
      .catch(error => {
        console.error('Service Worker registration failed:', error);
      });
  }
});
