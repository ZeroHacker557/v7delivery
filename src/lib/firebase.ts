import { initializeApp } from 'firebase/app'
import { getFirestore, collection, onSnapshot, query, where, doc, updateDoc, writeBatch, getDocs, getDoc } from 'firebase/firestore'
import { getStorage } from 'firebase/storage'
import { firebaseConfig } from '../config/firebase'
import { parseDate } from '../utils/date'
import type { Product, Category, Order, PaymentSettings, DeliverySettings, Notification, UserProfile } from '../types/domain'

// Initialize Firebase
export const app = initializeApp(firebaseConfig)
export const db = getFirestore(app)
export const storage = getStorage(app)

// Real-time Firestore Listeners
export function subscribeToProducts(callback: (products: Product[]) => void, onError?: (err: unknown) => void) {
  console.log('[Firebase] Subscribing to products collection...')
  const productsRef = collection(db, 'products')
  return onSnapshot(productsRef, (snapshot) => {
    console.log(`[Firebase] Products snapshot received: ${snapshot.size} documents`)
    const products: Product[] = snapshot.docs.map((doc) => {
      const data = doc.data()
      const rawId = data.id || doc.id
      const numId = typeof rawId === 'number' ? rawId : (parseInt(String(rawId), 10) || Math.abs(hashString(doc.id)))
      
      return {
        id: numId,
        name: data.name || '',
        price: Number(data.price) || 0,
        oldPrice: data.oldPrice ? Number(data.oldPrice) : undefined,
        category: data.category || '',
        images: data.images || [],
        rating: data.rating || 5,
        reviews: data.reviews || 0,
        sizes: data.sizes || [],
        color: data.color || '',
        description: data.description || '',
        discount: data.discount || '',
        stock: typeof data.stock === 'number' ? data.stock : undefined
      }
    })
    callback(products)
  }, (error) => {
    console.error('[Firebase] Products snapshot ERROR:', error)
    console.error('[Firebase] This usually means Firestore Security Rules are blocking read access.')
    console.error('[Firebase] Go to Firebase Console → Firestore → Rules and set: allow read: if true;')
    if (onError) onError(error)
  })
}

export function subscribeToCategories(callback: (categories: Category[]) => void, onError?: (err: unknown) => void) {
  console.log('[Firebase] Subscribing to categories collection...')
  const categoriesRef = collection(db, 'categories')
  return onSnapshot(categoriesRef, (snapshot) => {
    console.log(`[Firebase] Categories snapshot received: ${snapshot.size} documents`)
    const categories: Category[] = snapshot.docs.map((doc) => {
      const data = doc.data()
      const rawId = data.id || doc.id
      const numId = typeof rawId === 'number' ? rawId : (parseInt(String(rawId), 10) || Math.abs(hashString(doc.id)))
      
      return {
        id: numId,
        name: data.name || '',
        icon: data.icon || 'package'
      }
    })
    callback(categories)
  }, (error) => {
    console.error('[Firebase] Categories snapshot ERROR:', error)
    console.error('[Firebase] This usually means Firestore Security Rules are blocking read access.')
    if (onError) onError(error)
  })
}

function hashString(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i)
    hash |= 0
  }
  return hash
}

// ── ORDERS ───────────────────────────────────────────────────

// Buyurtmani mijoz emas, SERVER yaratadi: POST /api/orders.
// Narx, chegirma va jami Firestore'dagi haqiqiy qiymatlardan
// qayta hisoblanadi, shuning uchun bu yerda addDoc yo'q (F-04).

// ── PAYMENT SETTINGS ─────────────────────────────────────────

const PAYMENT_FALLBACK: PaymentSettings = {
  cardNumber: '',
  cardOwner: '',
}

const DELIVERY_FALLBACK: DeliverySettings = { fee: 0, freeFrom: 0 }

/** Yetkazib berish narxi — settings/delivery hujjatidan. */
export async function getDeliverySettings(): Promise<DeliverySettings> {
  try {
    const snap = await getDoc(doc(db, 'settings', 'delivery'))
    if (!snap.exists()) return DELIVERY_FALLBACK
    const data = snap.data()
    return {
      fee: Math.max(Number(data.fee) || 0, 0),
      freeFrom: Math.max(Number(data.freeFrom) || 0, 0),
    }
  } catch (error) {
    console.error("[Firebase] Yetkazish sozlamalarini o'qib bo'lmadi:", error)
    return DELIVERY_FALLBACK
  }
}

/** Karta ma'lumoti yagona manbadan — settings/payment hujjatidan (F-07). */
export async function getPaymentSettings(): Promise<PaymentSettings> {
  try {
    const snap = await getDoc(doc(db, 'settings', 'payment'))
    if (!snap.exists()) return PAYMENT_FALLBACK
    const data = snap.data()
    return {
      cardNumber: String(data.cardNumber || PAYMENT_FALLBACK.cardNumber),
      cardOwner: String(data.cardOwner || PAYMENT_FALLBACK.cardOwner),
    }
  } catch (error) {
    console.error("[Firebase] To'lov sozlamalarini o'qib bo'lmadi:", error)
    return PAYMENT_FALLBACK
  }
}

// Foydalanuvchi hujjatini /api/auth yaratadi va yangilaydi.

export function subscribeToUserProfile(userId: number, callback: (profile: UserProfile | null) => void) {
  const userRef = doc(db, 'users', String(userId))
  
  return onSnapshot(userRef, (snapshot) => {
    if (snapshot.exists()) {
      callback(snapshot.data() as UserProfile)
    } else {
      callback(null)
    }
  }, (error) => {
    console.error("Error fetching user profile:", error)
  })
}

export async function updateUserProfile(userId: number, data: Partial<UserProfile>) {
  try {
    const userRef = doc(db, 'users', String(userId))
    await updateDoc(userRef, data)
  } catch (error) {
    console.error("Error updating user profile:", error)
  }
}

// Subscribe to User Orders
export function subscribeToUserOrders(userId: number, callback: (orders: Order[]) => void) {
  const ordersRef = collection(db, 'orders')
  // We only use 'where' to avoid requiring a composite index in Firestore.
  // Sorting will be done on the client side.
  const q = query(ordersRef, where('userId', '==', userId))
  
  return onSnapshot(q, (snapshot) => {
    const orders = snapshot.docs.map((snap) => {
      const data = snap.data()
      return {
        ...data,
        // Haqiqiy kalit — hujjat identifikatori (F-03)
        id: snap.id,
        // Eski buyurtmalarda orderNumber yo'q: o'sha paytdagi "#1234567" ni ko'rsatamiz
        orderNumber: data.orderNumber || data.id || snap.id,
        createdAt: data.createdAt || '',
      } as Order
    })

    orders.sort((a, b) => parseDate(b.createdAt) - parseDate(a.createdAt))

    callback(orders)
  }, (error) => {
    console.error("Error fetching user orders:", error)
  })
}

// ── REVIEWS ──────────────────────────────────────────────────
import type { Review } from '../types/domain'

// Sharhni /api/reviews yaratadi — mijoz to'g'ridan-to'g'ri yoza olmaydi.

export function subscribeToProductReviews(productId: number, callback: (reviews: Review[]) => void) {
  const reviewsRef = collection(db, 'reviews')
  const q = query(reviewsRef, where('productId', '==', productId))
  
  return onSnapshot(q, (snapshot) => {
    const reviews: Review[] = snapshot.docs.map(doc => ({
      ...doc.data(),
      id: doc.id
    } as Review))
    // sort by newest
    reviews.sort((a, b) => parseDate(b.date) - parseDate(a.date))
    callback(reviews)
  }, (error) => {
    console.error("Error fetching product reviews:", error)
  })
}

export function subscribeToUserReviews(userId: number, callback: (reviews: Review[]) => void) {
  const reviewsRef = collection(db, 'reviews')
  const q = query(reviewsRef, where('userId', '==', userId))
  
  return onSnapshot(q, (snapshot) => {
    const reviews: Review[] = snapshot.docs.map(doc => ({
      ...doc.data(),
      id: doc.id
    } as Review))
    // sort by newest
    reviews.sort((a, b) => parseDate(b.date) - parseDate(a.date))
    callback(reviews)
  }, (error) => {
    console.error("Error fetching user reviews:", error)
  })
}

// ==========================================
// NOTIFICATIONS
// ==========================================

export function subscribeToUserNotifications(userId: number, callback: (notifications: Notification[]) => void) {
  const q = query(
    collection(db, 'notifications'),
    where('userId', '==', userId)
  )
  return onSnapshot(q, (snapshot) => {
    const notifs = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as Notification))
    // ISO sana bo'yicha saralash; eski formatlar oxiriga tushadi (F-10)
    notifs.sort((a, b) => parseDate(b.date) - parseDate(a.date))
    callback(notifs)
  }, (error) => {
    console.error("Error fetching notifications:", error)
  })
}

export async function markNotificationsAsRead(userId: number) {
  try {
    const q = query(
      collection(db, 'notifications'),
      where('userId', '==', userId),
      where('read', '==', false)
    )
    const snapshot = await getDocs(q)
    const batch = writeBatch(db)
    snapshot.docs.forEach(docSnap => {
      batch.update(docSnap.ref, { read: true })
    })
    await batch.commit()
  } catch (e) {
    console.error('Error marking notifications as read', e)
  }
}
