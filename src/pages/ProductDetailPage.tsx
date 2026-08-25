import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowLeft, Heart, Minus, MessageSquare, Plus, ShoppingCart, Star, Truck, UserRound } from 'lucide-react'
import { formatPrice } from '../data'
import { getImageUrl, hapticSuccess, getTelegramUser, showAlert } from '../utils/telegram'
import { formatDate } from '../utils/date'
import { CartButton } from '../components/ui/CartButton'
import { subscribeToProductReviews } from '../lib/firebase'
import { apiPost, ApiError } from '../lib/api'
import { track } from '../lib/track'
import { useT } from '../i18n'
import type { Product, Review } from '../types/domain'

type Props = {
  product: Product
  onAddToCart: (product: Product, size?: string, color?: string) => void
  onBack: () => void
  likedIds: number[]
  onToggleLike: (id: number) => void
  onOpenCart: () => void
  cartCount: number
  /** Savat yoki qidiruv ochiq bo'lsa pastki panel ularni to'sib qo'ymasligi kerak. */
  hideBottomBar?: boolean
}

export function ProductDetailPage({
  product, onAddToCart, onBack, likedIds, onToggleLike, onOpenCart, cartCount, hideBottomBar = false,
}: Props) {
  const t = useT()
  const [activeImage, setActiveImage] = useState(0)
  const [count, setCount] = useState(1)

  const colorsList = product.colors
    || (product.color ? product.color.split(',').map((c) => c.trim()).filter(Boolean) : [])
  const [selectedSize, setSelectedSize] = useState(product.sizes?.[0] || '')
  const [selectedColor, setSelectedColor] = useState(colorsList[0] || '')

  const favourite = likedIds.includes(product.id)
  const images = product.images || []
  const stock = product.stock
  const soldOut = stock === 0
  const lowStock = typeof stock === 'number' && stock > 0 && stock <= 5
  const maxCount = typeof stock === 'number' && stock > 0 ? Math.min(stock, 99) : 99

  const [reviews, setReviews] = useState<Review[]>([])
  const [userRating, setUserRating] = useState(0)
  const [userComment, setUserComment] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [reviewNotice, setReviewNotice] = useState('')
  const tgUser = getTelegramUser()

  useEffect(() => {
    const unsub = subscribeToProductReviews(product.id, setReviews)
    return () => unsub()
  }, [product.id])

  // Analitika: mahsulot ko'rildi (12-band)
  useEffect(() => {
    track('view', product.id)
  }, [product.id])

  const avgRating = reviews.length > 0
    ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(1)
    : product.rating.toFixed(1)
  const reviewCount = reviews.length > 0 ? reviews.length : product.reviews

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!tgUser) return showAlert(t('profile.userNotFound'))
    if (userRating === 0) return showAlert(t('reviews.needRating'))

    setIsSubmitting(true)
    setReviewNotice('')
    try {
      // Server sotib olganini tekshiradi va mahsulot reytingini
      // qayta hisoblaydi (9- va 10-bandlar)
      await apiPost('/api/reviews', {
        productId: product.id,
        rating: userRating,
        comment: userComment.trim(),
      })
      hapticSuccess()
      setUserRating(0)
      setUserComment('')
      setReviewNotice(t('reviews.thanks'))
    } catch (error) {
      setReviewNotice(error instanceof ApiError ? error.message : t('reviews.error'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleAddToCart = () => {
    if (soldOut) return
    for (let i = 0; i < count; i++) onAddToCart(product, selectedSize, selectedColor)
    setCount(1)
  }

  return (
    <>
      <header className="flex items-center justify-between px-5 pt-8 sm:px-10 page-animate">
        <button onClick={onBack} className="icon-button" aria-label={t('common.back')}>
          <ArrowLeft size={22} />
        </button>
        <h2 className="text-lg font-bold" style={{ color: 'var(--ink)' }}>{t('product.title')}</h2>
        <div className="flex gap-1">
          <button
            onClick={() => onToggleLike(product.id)}
            className="icon-button"
            style={{ color: favourite ? 'var(--brand)' : 'var(--ink)' }}
            aria-label={t('favorites.title')}
            aria-pressed={favourite}
          >
            <Heart size={21} fill={favourite ? 'currentColor' : 'none'} />
          </button>
          <CartButton count={cartCount} onClick={onOpenCart} />
        </div>
      </header>

      {/* Rasm galereyasi */}
      <section className="relative mx-auto mt-3 max-w-3xl px-5" style={{ animation: 'fadeInUp 0.4s ease' }}>
        {product.discount && !soldOut && (
          <span
            className="absolute left-8 top-3 z-10 rounded-lg px-2.5 py-1 text-xs font-bold"
            style={{ background: 'var(--brand-strong)', color: 'var(--brand-ink)' }}
          >
            {product.discount}
          </span>
        )}
        {/*
          * Rasm ABSOLYUT joylashtirilgan, `place-items-center` grid ichida emas.
          * Grid markazlashtirilganda element cho'zilmaydi va bolaning
          * `height: 100%` foizi hal bo'lmay `auto` ga tushadi — bo'yi baland
          * rasm konteynerdan oshib ketib, `overflow-hidden` uni pastidan
          * kesib qo'yadi. `inset-0` esa aniq quti beradi, `object-contain`
          * shu qutiga to'liq sig'diradi.
          */}
        <div
          className="relative mx-auto h-[280px] w-full overflow-hidden rounded-2xl sm:h-[380px]"
          style={{ background: 'var(--surface-2)', opacity: soldOut ? 0.55 : 1 }}
        >
          {images[activeImage] ? (
            <img
              className="absolute inset-0 size-full object-contain p-4"
              src={getImageUrl(images[activeImage])}
              alt={product.name}
              decoding="async"
            />
          ) : (
            <span className="absolute inset-0 grid place-items-center">
              <ShoppingCart size={56} style={{ color: 'var(--faint)' }} />
            </span>
          )}
        </div>
        {images.length > 1 && (
          <div className="mt-3 flex justify-center gap-2">
            {images.map((_, i) => (
              <button
                key={i}
                onClick={() => setActiveImage(i)}
                className={'dot ' + (activeImage === i ? 'active' : '')}
                aria-label={`${i + 1}`}
              />
            ))}
          </div>
        )}
      </section>

      <section className="mx-5 mt-5 pb-40 sm:mx-10 page-animate">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-bold" style={{ color: 'var(--brand)' }}>{product.category}</span>
          <span
            className="flex items-center gap-2 rounded-2xl px-3.5 py-2 text-sm font-bold"
            style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
          >
            <Truck size={17} /> {t('product.fastDelivery')}
          </span>
        </div>

        <h1 className="mt-4 text-2xl font-extrabold sm:text-3xl" style={{ color: 'var(--ink)', textWrap: 'balance' }}>
          {product.name}
        </h1>

        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm" style={{ color: 'var(--muted)' }}>
          <Star size={18} fill="var(--warning)" style={{ color: 'var(--warning)' }} />
          {avgRating} ({t('product.ratingCount', { count: reviewCount })})
        </p>

        <div className="mt-5 flex items-baseline gap-3">
          <strong className="text-3xl" style={{ color: 'var(--ink)' }}>{formatPrice(product.price)}</strong>
          {product.oldPrice && <del style={{ color: 'var(--faint)' }}>{formatPrice(product.oldPrice)}</del>}
        </div>

        {soldOut && (
          <p
            className="mt-3 inline-block rounded-xl px-3 py-2 text-sm font-bold"
            style={{ background: 'var(--surface-3)', color: 'var(--muted)' }}
          >
            {t('product.soldOutLong')}
          </p>
        )}
        {lowStock && (
          <p
            className="mt-3 inline-block rounded-xl px-3 py-2 text-sm font-bold"
            style={{ background: 'var(--warning-soft)', color: 'var(--warning)' }}
          >
            {t('product.lowStock', { count: stock! })}
          </p>
        )}

        {colorsList.length > 0 && (
          <section className="detail-panel">
            <b style={{ color: 'var(--ink)' }}>{t('product.chooseColor')}</b>
            <div className="mt-4 flex flex-wrap gap-3">
              {colorsList.map((c) => (
                <button
                  onClick={() => setSelectedColor(c)}
                  className={'size-chip px-4 ' + (selectedColor === c ? 'active' : '')}
                  key={c}
                >
                  <b>{c}</b>
                </button>
              ))}
            </div>
          </section>
        )}

        {product.sizes && product.sizes.length > 0 && (
          <section className="detail-panel">
            <b style={{ color: 'var(--ink)' }}>{t('product.chooseSize')}</b>
            <div className="mt-4 grid grid-cols-4 gap-3 sm:grid-cols-7">
              {product.sizes.map((s) => (
                <button
                  onClick={() => setSelectedSize(s)}
                  className={'size-chip ' + (selectedSize === s ? 'active' : '')}
                  key={s}
                >
                  <b>{s}</b>
                </button>
              ))}
            </div>
          </section>
        )}

        {product.description && (
          <section className="detail-panel">
            <b style={{ color: 'var(--ink)' }}>{t('product.about')}</b>
            <p className="mt-4 text-sm leading-7" style={{ color: 'var(--muted)' }}>{product.description}</p>
          </section>
        )}

        {/* Sharhlar */}
        <section className="mt-8">
          <h3 className="text-xl font-bold" style={{ color: 'var(--ink)' }}>{t('reviews.title')}</h3>

          <form
            onSubmit={handleSubmitReview}
            className="mt-5 rounded-2xl border p-4"
            style={{ borderColor: 'var(--line)', background: 'var(--surface-2)' }}
          >
            <p className="mb-2 text-sm font-bold" style={{ color: 'var(--ink-2)' }}>{t('reviews.rateThis')}</p>
            <div className="mb-4 flex gap-2">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setUserRating(star)}
                  className="transition hover:scale-110 active:scale-95"
                  aria-label={`${star}`}
                >
                  <Star
                    size={28}
                    fill={star <= userRating ? 'var(--warning)' : 'none'}
                    style={{ color: star <= userRating ? 'var(--warning)' : 'var(--line)' }}
                  />
                </button>
              ))}
            </div>

            <div className="field items-start">
              <MessageSquare size={19} className="mt-0.5 shrink-0" style={{ color: 'var(--faint)' }} />
              <textarea
                value={userComment}
                onChange={(e) => setUserComment(e.target.value)}
                placeholder={t('reviews.placeholder')}
                rows={2}
                className="resize-none text-sm"
              />
            </div>

            <button type="submit" disabled={isSubmitting || userRating === 0} className="btn-primary mt-4 w-full py-3 text-sm">
              {isSubmitting ? t('reviews.submitting') : t('reviews.submit')}
            </button>

            {reviewNotice && (
              <p className="mt-3 text-center text-xs font-bold" style={{ color: 'var(--muted)' }}>
                {reviewNotice}
              </p>
            )}
          </form>

          <div className="mt-6 space-y-4">
            {reviews.length === 0 ? (
              <p className="py-4 text-center text-sm" style={{ color: 'var(--muted)' }}>{t('reviews.empty')}</p>
            ) : (
              reviews.map((review) => (
                <div
                  key={review.id}
                  className="border-b pb-4 last:border-0 last:pb-0"
                  style={{ borderColor: 'var(--line-soft)' }}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="grid size-8 place-items-center rounded-full"
                      style={{ background: 'var(--surface-3)', color: 'var(--muted)' }}
                    >
                      <UserRound size={16} />
                    </div>
                    <div>
                      <p className="text-sm font-bold" style={{ color: 'var(--ink)' }}>{review.userName}</p>
                      <p className="text-xs" style={{ color: 'var(--faint)' }}>{formatDate(review.date)}</p>
                    </div>
                    <div className="ml-auto flex gap-0.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <Star
                          key={star}
                          size={13}
                          fill={star <= review.rating ? 'var(--warning)' : 'none'}
                          style={{ color: star <= review.rating ? 'var(--warning)' : 'var(--line)' }}
                        />
                      ))}
                    </div>
                  </div>
                  {review.comment && (
                    <p className="ml-10 mt-2 text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                      {review.comment}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </section>
      </section>

      {/* Pastki panel — modal ochiq bo'lsa chizilmaydi */}
      {!hideBottomBar && createPortal(
        <div
          className="fixed bottom-0 left-0 right-0 z-[100] border-t p-4"
          style={{
            borderColor: 'var(--line)',
            background: 'color-mix(in srgb, var(--surface) 94%, transparent)',
            backdropFilter: 'blur(12px)',
            paddingBottom: 'calc(1rem + var(--safe-bottom))',
          }}
        >
          <div className="mx-auto flex max-w-[1120px] items-center gap-3">
            <div className="hidden sm:block">
              <b className="text-xl" style={{ color: 'var(--ink)' }}>{formatPrice(product.price)}</b>
            </div>
            <div className="flex items-center gap-2 rounded-2xl p-1.5" style={{ background: 'var(--surface-2)' }}>
              <button
                onClick={() => setCount(Math.max(1, count - 1))}
                className="grid size-8 place-items-center rounded-lg transition active:scale-90"
                style={{ color: 'var(--ink)' }}
                aria-label="-"
              >
                <Minus size={18} />
              </button>
              <b className="w-5 text-center" style={{ color: 'var(--ink)' }}>{count}</b>
              <button
                onClick={() => setCount(Math.min(maxCount, count + 1))}
                disabled={count >= maxCount}
                className="grid size-8 place-items-center rounded-lg transition active:scale-90 disabled:opacity-40"
                style={{ color: 'var(--ink)' }}
                aria-label="+"
              >
                <Plus size={18} />
              </button>
            </div>
            <button onClick={handleAddToCart} disabled={soldOut} className="btn-primary ml-auto flex-1 py-3.5">
              <ShoppingCart size={20} />
              <span className="text-sm sm:text-base">
                {soldOut ? t('product.soldOut') : t('product.addToCart')}
              </span>
            </button>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
