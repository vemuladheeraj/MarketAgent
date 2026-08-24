import { initializeApp, getApps, getApp } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';

export const firebaseConfig = {
  apiKey: "AIzaSyCA_X0JwKNlasWfl5bV8F8y1pqHMzHOSBQ",
  authDomain: "marketagent-9ea8f.firebaseapp.com",
  projectId: "marketagent-9ea8f",
  storageBucket: "marketagent-9ea8f.firebasestorage.app",
  messagingSenderId: "54752451518",
  appId: "1:54752451518:web:cf1458cfa69df5260737ef",
  measurementId: "G-PH30FYVNB0"
};

// Initialize Firebase App singleton
export const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const db = getFirestore(app);
