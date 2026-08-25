import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { subscribeToCategories, subscribeToProducts, subscribeToUserOrders, subscribeToUserProfile, subscribeToUserNotifications, markNotificationsAsRead } from '../lib/firebase'
import { ensureSignedIn, onAuthChanged, auth } from '../lib/auth'
import { apiPost, ApiError } from '../lib/api'
import { track } from '../lib/track'
import { searchProducts } from '../utils/search'
import type { AppPage, Category, Order, OrderForm, Product, UserProfile, Notification } from '../types/domain'
import { hapticError, hapticFeedback, hapticSuccess, initTelegram } from '../utils/telegram'
import { applyTheme, getStoredTheme, storeTheme, type ThemeMode } from '../utils/theme'
import { useT } from '../i18n'

/** Pastki menyudagi asosiy sahifalar — ularga o'tganda tarix tozalanadi. */
const ROOT_PAGES: AppPage[] = ['home', 'catalog', 'favorites', 'orders', 'profile']

const LIKES_KEY = 'v7ShopLikes'
const CART_KEY = 'v7ShopCart'

type CartItems = Record<string, { quantity: number; size?: string; color?: string }>

function loadLikes(): number[] {
  try {
    return JSON.parse(localStorage.getItem(LIKES_KEY) || '[]')
  } catch { return [] }
}

function saveLikes(ids: number[]) {
  localStorage.setItem(LIKES_KEY, JSON.stringify(ids))
}

/** Savat saqlanadi: Telegram mini app'ni yopib-ochganda yo'qolmasligi uchun (F-14). */
/** Takroriy buyurtmani to'sish uchun noyob kalit. */
function newOrderKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function loadCart(): CartItems {
  try {
    const raw = JSON.parse(localStorage.getItem(CART_KEY) || '{}')
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
    return raw as CartItems
  } catch { return {} }
}

export function useShopStore() {
  const t = useT()
  const [page, setPage] = useState<AppPage>('home')
  // Telegram BackButton shu tarix bo'yicha ishlaydi (D-03)
  const [history, setHistory] = useState<AppPage[]>([])
  // Bosh sahifadan tanlangan kategoriya katalogga uzatiladi (F-16)
  const [catalogCategory, setCatalogCategory] = useState<string | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [likedIds, setLikedIds] = useState<number[]>(loadLikes)
  const [cartItems, setCartItems] = useState<CartItems>(loadCart)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [isSearchOpen, setSearchOpen] = useState(false)
  const [isCartOpen, setCartOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [myOrders, setMyOrders] = useState<Order[]>([])
  const [checkoutDone, setCheckoutDone] = useState(false)
  const [isSubmitting, setSubmitting] = useState(false)
  const [authReady, setAuthReady] = useState(false)
  const [theme, setThemeState] = useState<ThemeMode>(getStoredTheme)
  // Bitta rasmiylashtirish uchun bitta kalit. Xato bo'lsa saqlanadi —
  // qayta urinishda server yangi buyurtma yaratmaydi.
  const orderKeyRef = useRef<string | null>(null)
  const [isAuthenticated, setAuthenticated] = useState(false)
  const [orderForm, setOrderForm] = useState<OrderForm>({
    name: '', phone: '', address: '', location: null, comment: '', paymentMethod: 'Naqd',
  })
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadNotificationsCount, setUnreadNotificationsCount] = useState(0)

  // Ochiq ma'lumot: katalog. Auth kutilmaydi — Rules'da o'qish ochiq.
  useEffect(() => {
    initTelegram()

    const unsubProds = subscribeToProducts(
      (fbProducts) => {
        setProducts(fbProducts)
        setLoading(false)
      },
      () => setLoading(false),
    )

    const unsubCats = subscribeToCategories(
      (fbCats) => setCategories(fbCats),
      () => {},
    )

    return () => {
      unsubProds()
      unsubCats()
    }
  }, [])

  // Shaxsiy ma'lumot: faqat Telegram imzosi tekshirilgandan keyin (F-02).
  // Tizimga kirmagan holatda Rules bu kolleksiyalarni bermaydi, shuning
  // uchun umuman obuna bo'lmaymiz.
  useEffect(() => {
    ensureSignedIn()

    let unsubOrders: (() => void) | undefined
    let unsubProfile: (() => void) | undefined
    let unsubNotifications: (() => void) | undefined

    const stopAll = () => {
      unsubOrders?.()
      unsubProfile?.()
      unsubNotifications?.()
      unsubOrders = undefined
      unsubProfile = undefined
      unsubNotifications = undefined
    }

    const unsubAuth = onAuthChanged((user) => {
      stopAll()

      if (!user) {
        setAuthReady(true)
        setAuthenticated(false)
        setUserProfile(null)
        setMyOrders([])
        setNotifications([])
        setUnreadNotificationsCount(0)
        return
      }

      const userId = Number(user.uid)
      setAuthReady(true)
      setAuthenticated(true)

      unsubOrders = subscribeToUserOrders(userId, setMyOrders)
      unsubProfile = subscribeToUserProfile(userId, (profile) => {
        if (profile) setUserProfile(profile as UserProfile)
      })
      unsubNotifications = subscribeToUserNotifications(userId, (notifs) => {
        setNotifications(notifs)
        setUnreadNotificationsCount(notifs.filter((n: Notification) => !n.read).length)
      })
    })

    return () => {
      unsubAuth()
      stopAll()
    }
  }, [])

  // Savat har o'zgarganda saqlanadi (F-14)
  useEffect(() => {
    try {
      localStorage.setItem(CART_KEY, JSON.stringify(cartItems))
    } catch (error) {
      console.warn("[Savat] saqlab bo'lmadi:", error)
    }
  }, [cartItems])

  const cartCount = Object.values(cartItems).reduce((total, item) => total + item.quantity, 0)

  const cartTotal = useMemo(() => {
    return Object.entries(cartItems).reduce((sum, [key, item]) => {
      const pId = Number(key.split('_')[0])
      const p = products.find((pr) => String(pr.id) === String(pId))
      return sum + (p ? p.price * item.quantity : 0)
    }, 0)
  }, [cartItems, products])

  const cartProducts = useMemo(() => {
    return Object.entries(cartItems)
      .map(([key, item]) => {
        const pId = Number(key.split('_')[0])
        const p = products.find((pr) => String(pr.id) === String(pId))
        return p ? { product: p, quantity: item.quantity, size: item.size, color: item.color, cartKey: key } : null
      })
      .filter(Boolean) as { product: Product; quantity: number; size?: string; color?: string; cartKey: string }[]
  }, [cartItems, products])

  const searchResults = useMemo(
    () => searchProducts(products, query),
    [query, products],
  )

  const navigate = useCallback((nextPage: AppPage) => {
    const uid = auth.currentUser?.uid
    if (nextPage === 'notifications' && uid) {
      markNotificationsAsRead(Number(uid))
    }

    setPage((current) => {
      if (current === nextPage) return current
      // Asosiy bo'limga o'tilsa tarix tozalanadi, ichki sahifada esa
      // qayerdan kelganimiz eslab qolinadi.
      setHistory((h) =>
        ROOT_PAGES.includes(nextPage) ? [] : [...h.slice(-19), current],
      )
      return nextPage
    })

    setCartOpen(false)
    setSearchOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const setTheme = useCallback((mode: ThemeMode) => {
    setThemeState(mode)
    storeTheme(mode)
    applyTheme(mode)
    hapticFeedback('light')
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const next: ThemeMode = current === 'dark' ? 'light' : 'dark'
      storeTheme(next)
      applyTheme(next)
      return next
    })
    hapticFeedback('light')
  }, [])

  /** Bosh sahifadagi kategoriya bosilganda katalogni filtrlab ochamiz. */
  const openCategory = useCallback((category: string) => {
    setCatalogCategory(category)
    setPage((current) => {
      setHistory(() => (current === 'catalog' ? [] : []))
      return 'catalog'
    })
    setCartOpen(false)
    setSearchOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    hapticFeedback('light')
  }, [])

  /** Orqaga: avval ochiq oyna yopiladi, keyin sahifa tarixi. */
  const goBack = useCallback(() => {
    if (isSearchOpen) {
      setSearchOpen(false)
      return
    }
    if (isCartOpen) {
      setCartOpen(false)
      return
    }
    setHistory((h) => {
      if (h.length === 0) return h
      setPage(h[h.length - 1])
      window.scrollTo({ top: 0 })
      return h.slice(0, -1)
    })
  }, [isSearchOpen, isCartOpen])

  const openProduct = useCallback((product: Product) => {
    setSelectedProduct(product)
    setCartOpen(false)
    setPage((current) => {
      setHistory((h) => [...h.slice(-19), current])
      return 'detail'
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
    hapticFeedback('light')
  }, [])

  const toggleLike = useCallback((id: number) => {
    setLikedIds((current) => {
      const next = current.includes(id) ? current.filter((i) => i !== id) : [...current, id]
      saveLikes(next)
      hapticFeedback('light')
      return next
    })
  }, [])

  const notify = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(null), 2600)
  }, [])

  const addToCart = useCallback((product: Product, size?: string, color?: string) => {
    const s = size || product.sizes?.[0] || 'nosize'
    const c = color || product.color || 'nocolor'
    const key = `${product.id}_${s}_${c}`
    setCartItems((current) => ({
      ...current,
      [key]: {
        quantity: (current[key]?.quantity ?? 0) + 1,
        size: size || product.sizes?.[0],
        color: color || product.color
      }
    }))
    notify(t('product.addedToCart', { name: product.name }))
    hapticFeedback('medium')
    track('cart_add', product.id)
  }, [notify, t])

  const updateCartQuantity = useCallback((cartKey: string, nextQuantity: number) => {
    setCartItems((current) => {
      const next = { ...current }
      if (nextQuantity <= 0) delete next[cartKey]
      else next[cartKey] = { ...next[cartKey], quantity: nextQuantity }
      return next
    })
    hapticFeedback('light')
  }, [])

  const openCart = useCallback(() => setCartOpen(true), [])
  const closeCart = useCallback(() => setCartOpen(false), [])

  const goToCheckout = useCallback(() => {
    track('checkout_start')
    setCartOpen(false)
    setPage((current) => {
      setHistory((h) => [...h.slice(-19), current])
      return 'checkout'
    })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const updateOrderForm = useCallback((field: keyof OrderForm, value: unknown) => {
    setOrderForm((prev) => ({ ...prev, [field]: value }))
  }, [])

  /**
   * Buyurtmani SERVER yaratadi (F-04). Bu yerdan faqat "nimadan nechta"
   * yuboriladi — narx, chegirma va jami serverda qayta hisoblanadi,
   * shuning uchun finalTotal parametri endi kerak emas.
   */
  const submitOrder = useCallback(async () => {
    if (isSubmitting) return false

    if (!orderForm.name.trim() || !orderForm.phone.trim() || !orderForm.address.trim()) {
      notify(t('checkout.fillAll'))
      return false
    }

    if (cartProducts.length === 0) {
      notify(t('checkout.cartEmpty'))
      return false
    }

    if (!orderKeyRef.current) orderKeyRef.current = newOrderKey()

    setSubmitting(true)
    try {
      await apiPost<{ id: string; orderNumber: string; total: number }>('/api/orders', {
        clientOrderId: orderKeyRef.current,
        items: cartProducts.map(({ product, quantity, size, color }) => ({
          productId: product.id,
          quantity,
          size,
          color,
        })),
        customer: {
          name: orderForm.name.trim(),
          phone: orderForm.phone.trim(),
          address: orderForm.address.trim(),
          location: orderForm.location,
          comment: orderForm.comment,
          paymentMethod: orderForm.paymentMethod,
        },
        promoCode: orderForm.promoCode,
      })
    } catch (error) {
      // Buyurtma yaratilmadi — savat SAQLANIB qoladi (F-05)
      console.error('[Buyurtma] yuborilmadi:', error)
      hapticError()
      notify(error instanceof ApiError ? error.message : t('checkout.failed'))
      return false
    } finally {
      setSubmitting(false)
    }

    orderKeyRef.current = null
    setCartItems({})
    setOrderForm({ name: '', phone: '', address: '', location: null, comment: '', paymentMethod: 'Naqd' })
    setCheckoutDone(true)
    hapticSuccess()
    notify(t('checkout.success'))
    setTimeout(() => setCheckoutDone(false), 4000)

    return true
  }, [isSubmitting, orderForm, cartProducts, notify, t])

  return {
    page, history, canGoBack: history.length > 0 || isCartOpen || isSearchOpen,
    products, categories, loading,
    cartItems, cartCount, cartTotal, cartProducts,
    likedIds, selectedProduct,
    isSearchOpen, isCartOpen, query, searchResults, toast,
    myOrders, checkoutDone, isSubmitting, authReady, isAuthenticated, orderForm, userProfile,
    notifications, unreadNotificationsCount,
    catalogCategory, openCategory,
    theme, setTheme, toggleTheme,
    navigate, goBack, openProduct, toggleLike,
    setSearchOpen, setQuery,
    addToCart, updateCartQuantity,
    openCart, closeCart, goToCheckout,
    updateOrderForm, submitOrder,
    notify, clearToast: () => setToast(null),
  }
}
