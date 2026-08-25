import { Suspense, lazy, useEffect } from 'react'
import { BottomNav } from './components/layout/BottomNav'
import { SearchOverlay } from './components/layout/SearchOverlay'
import { CartDrawer } from './components/cart/CartDrawer'
import { Toast } from './components/ui/Toast'
import { CheckoutSuccess } from './components/ui/CheckoutSuccess'
import { useShopStore } from './hooks/use-shop-store'
import { CatalogPage } from './pages/CatalogPage'
import { CheckoutPage } from './pages/CheckoutPage'
import { FavoritesPage } from './pages/FavoritesPage'
import { HomePage } from './pages/HomePage'
import { OrdersPage } from './pages/OrdersPage'
import { ProductDetailPage } from './pages/ProductDetailPage'
import { ProfilePage } from './pages/ProfilePage'
import { ProfileEditPage } from './pages/ProfileEditPage'
import { ReviewsPage } from './pages/ReviewsPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { LanguagePage } from './pages/LanguagePage'
import { SupportPage } from './pages/SupportPage'
import { setupBackButton, toggleBackButton, watchSafeArea } from './utils/telegram'
import { useI18n } from './i18n'

// Xarita kutubxonasi (~150 KB) faqat manzil sahifasi ochilganda yuklanadi (P-01)
const AddressesPage = lazy(() =>
  import('./pages/AddressesPage').then((m) => ({ default: m.AddressesPage })),
)

/** Pastki menyu ko'rinmaydigan sahifalar. */
const FULLSCREEN_PAGES = [
  'detail', 'checkout', 'addresses', 'profile_edit', 'reviews', 'notifications', 'language', 'support',
]

function PageFallback() {
  return (
    <div className="flex justify-center py-24">
      <div
        className="size-8 animate-spin rounded-full border-4"
        style={{ borderColor: 'var(--brand-soft)', borderTopColor: 'var(--brand)' }}
      />
    </div>
  )
}

function App() {
  const shop = useShopStore()
  const { lang, setLang } = useI18n()

  const productActions = {
    onOpen: shop.openProduct,
    onAddToCart: shop.addToCart,
    likedIds: shop.likedIds,
    onToggleLike: shop.toggleLike,
  }

  // Telegram xavfsiz zonasi
  useEffect(() => watchSafeArea(), [])

  // Telegram BackButton — Android'ning tizim tugmasi ham shu bilan ishlaydi
  useEffect(() => setupBackButton(shop.goBack), [shop.goBack])
  useEffect(() => toggleBackButton(shop.canGoBack), [shop.canGoBack])

  // Profilda saqlangan til — boshqa qurilmada ham o'sha tilda ochiladi
  useEffect(() => {
    const saved = shop.userProfile?.language
    if (saved && saved !== lang && !localStorage.getItem('v7ShopLang')) {
      setLang(saved)
    }
  }, [shop.userProfile?.language, lang, setLang])

  const goToCatalog = () => shop.navigate('catalog')

  return (
    <main className="app-shell">
      <div className="app-container">
        {shop.isSearchOpen && (
          <SearchOverlay
            query={shop.query}
            results={shop.searchResults}
            onQueryChange={shop.setQuery}
            onClose={() => shop.setSearchOpen(false)}
            onOpenProduct={shop.openProduct}
          />
        )}

        {shop.isCartOpen && (
          <CartDrawer
            cartProducts={shop.cartProducts}
            cartTotal={shop.cartTotal}
            onClose={shop.closeCart}
            onUpdateQuantity={shop.updateCartQuantity}
            onCheckout={shop.goToCheckout}
            onGoToCatalog={goToCatalog}
          />
        )}

        {shop.toast && <Toast message={shop.toast} onClose={shop.clearToast} />}
        {shop.checkoutDone && <CheckoutSuccess onViewOrders={() => shop.navigate('orders')} />}

        <div className="page-wrapper">
          {shop.page === 'home' && (
            <div className="page-animate">
              <HomePage
                products={shop.products}
                categories={shop.categories}
                loading={shop.loading}
                {...productActions}
                cartCount={shop.cartCount}
                unreadNotificationsCount={shop.unreadNotificationsCount}
                onSearch={() => shop.setSearchOpen(true)}
                onNavigate={shop.navigate}
                onOpenCategory={shop.openCategory}
                onOpenCart={shop.openCart}
                onNotify={shop.notify}
              />
            </div>
          )}

          {shop.page === 'catalog' && (
            <div className="page-animate">
              <CatalogPage
                key={shop.catalogCategory ?? 'all'}
                products={shop.products}
                categories={shop.categories}
                loading={shop.loading}
                initialCategory={shop.catalogCategory}
                {...productActions}
                cartCount={shop.cartCount}
                onSearch={() => shop.setSearchOpen(true)}
                onOpenCart={shop.openCart}
              />
            </div>
          )}

          {shop.page === 'favorites' && (
            <div className="page-animate">
              <FavoritesPage
                products={shop.products}
                {...productActions}
                cartCount={shop.cartCount}
                onOpenCart={shop.openCart}
                onGoToCatalog={goToCatalog}
              />
            </div>
          )}

          {shop.page === 'orders' && (
            <div className="page-animate">
              <OrdersPage
                orders={shop.myOrders}
                authReady={shop.authReady}
                isAuthenticated={shop.isAuthenticated}
                cartCount={shop.cartCount}
                onSearch={() => shop.setSearchOpen(true)}
                onOpenCart={shop.openCart}
                onGoToCatalog={goToCatalog}
                onNotify={shop.notify}
              />
            </div>
          )}

          {shop.page === 'profile' && (
            <div className="page-animate">
              <ProfilePage
                profile={shop.userProfile}
                orders={shop.myOrders}
                theme={shop.theme}
                onToggleTheme={shop.toggleTheme}
                onNavigate={shop.navigate}
                onNotify={shop.notify}
              />
            </div>
          )}

          {shop.page === 'detail' && shop.selectedProduct && (
            <ProductDetailPage
              product={shop.selectedProduct}
              onAddToCart={shop.addToCart}
              onBack={shop.goBack}
              likedIds={shop.likedIds}
              onToggleLike={shop.toggleLike}
              onOpenCart={shop.openCart}
              cartCount={shop.cartCount}
              hideBottomBar={shop.isCartOpen || shop.isSearchOpen}
            />
          )}

          {shop.page === 'checkout' && (
            <CheckoutPage
              profile={shop.userProfile}
              cartProducts={shop.cartProducts}
              cartTotal={shop.cartTotal}
              orderForm={shop.orderForm}
              onUpdateForm={shop.updateOrderForm}
              onSubmit={shop.submitOrder}
              isSubmitting={shop.isSubmitting}
              onBack={shop.goBack}
              onNavigate={shop.navigate}
            />
          )}

          {shop.page === 'addresses' && (
            <div className="page-animate">
              <Suspense fallback={<PageFallback />}>
                <AddressesPage
                  profile={shop.userProfile}
                  onBack={shop.goBack}
                  onNotify={shop.notify}
                />
              </Suspense>
            </div>
          )}

          {shop.page === 'profile_edit' && (
            <div className="page-animate">
              <ProfileEditPage profile={shop.userProfile} onBack={shop.goBack} onNotify={shop.notify} />
            </div>
          )}

          {shop.page === 'reviews' && (
            <div className="page-animate">
              <ReviewsPage onBack={shop.goBack} />
            </div>
          )}

          {shop.page === 'language' && (
            <div className="page-animate">
              <LanguagePage onBack={shop.goBack} onNotify={shop.notify} />
            </div>
          )}

          {shop.page === 'notifications' && (
            <div className="page-animate">
              <NotificationsPage notifications={shop.notifications} onBack={shop.goBack} />
            </div>
          )}

          {shop.page === 'support' && (
            <div className="page-animate">
              <SupportPage onBack={shop.goBack} />
            </div>
          )}
        </div>

        {!FULLSCREEN_PAGES.includes(shop.page) && (
          <BottomNav page={shop.page} onNavigate={shop.navigate} cartCount={shop.cartCount} />
        )}
      </div>
    </main>
  )
}

export default App
