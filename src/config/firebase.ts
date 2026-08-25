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
  apiKey: 'AIzaSyB-JENf9xTOJcEF81-6KJxb0HnCyLmjkc0',
  authDomain: 'ecommercytest.firebaseapp.com',
  projectId: 'ecommercytest',
  storageBucket: 'ecommercytest.firebasestorage.app',
  messagingSenderId: '107932467075',
  appId: '1:107932467075:web:1d2740db24de18661c00b6',
  measurementId: 'G-TFYZD2LLN0',
}
