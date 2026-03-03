(function () {
  "use strict";

  const firebaseConfig = {
    apiKey: "AIzaSyAHMNxaKZ0TH4odKaqdS8IV_k0-Rgg_Zrs",
    authDomain: "asseri-1.firebaseapp.com",
    projectId: "asseri-1",
    storageBucket: "asseri-1.firebasestorage.app",
    messagingSenderId: "962505507485",
    appId: "1:962505507485:web:6f7d387c3d3fb420558a74",
  };

  // Default backend endpoint for Firebase-hosted frontend.
  // Override with window.APP_API_BASE or ?api=... when needed.
  const firebaseApiBase = "https://asserk-asseri.hf.space";

  window.ASSERI_FIREBASE_CONFIG = firebaseConfig;
  window.ASSERI_FIREBASE_API_BASE = firebaseApiBase;

  if (firebaseApiBase && !window.APP_API_BASE) {
    window.APP_API_BASE = firebaseApiBase;
  }

  if (!window.firebase || typeof window.firebase.initializeApp !== "function") {
    return;
  }

  try {
    if (!window.firebase.apps.length) {
      window.firebase.initializeApp(firebaseConfig);
    }
  } catch (error) {
    console.warn("Firebase init warning:", error && error.message ? error.message : error);
  }
})();
