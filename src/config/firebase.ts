/**
 * Firebase mijoz (web) konfiguratsiyasi.
 *
 * Bu qiymatlar MAXFIY EMAS — Firebase ularni brauzerga ataylab ochiq
 * beradi, himoya Firestore Rules va App Check tomonida. Shuning uchun
 * env o'zgaruvchi emas, oddiy konstanta: Vercel'da 7 ta o'zgaruvchini
 * to'ldirish o'rniga shu faylni almashtirish kifoya.
 *
 * Firebase Console → ⚙️ Project Settings → General → "Your apps" →
 * Web app → SDK setup and configuration → Config.
 *
 * DIQQAT: bu yerdagi projectId bot ishlatadigan service account
 * (bot/config.py → FIREBASE_KEY_FILE) bilan BIR XIL loyihaga tegishli
 * bo'lishi shart. Aks holda bot bir bazaga yozadi, ilova boshqasidan
 * o'qiydi va katalog bo'sh ko'rinadi.
 */
export const firebaseConfig = {
  apiKey: 'AIzaSyBrhJVW619BDWoPYrIVhEr6M5M8R5KvtmA',
  authDomain: 'v7-savdo.firebaseapp.com',
  projectId: 'v7-savdo',
  storageBucket: 'v7-savdo.firebasestorage.app',
  messagingSenderId: '307522319870',
  appId: '1:307522319870:web:dd8d9187dbdc9c4f1fbcaf',
  measurementId: 'G-VLWJ5BF9P5',
}
