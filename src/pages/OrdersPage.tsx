import { useMemo, useState } from 'react'
import { ChevronDown, ExternalLink, Loader2, ShoppingBag, SlidersHorizontal, X } from 'lucide-react'
import { formatPrice } from '../data'
import { getImageUrl, openBotDeepLink } from '../utils/telegram'
import { formatOrderDate } from '../utils/date'
import { apiPost, ApiError } from '../lib/api'
import { BRAND } from '../config/brand'
import { hapticSuccess, hapticError } from '../utils/telegram'
import { PageHeader } from '../components/layout/PageHeader'
import { useT, type TranslationKey } from '../i18n'
import type { Order, OrderStatus } from '../types/domain'


const TABS: { id: string; labelKey: TranslationKey }[] = [
  { id: 'all', labelKey: 'orders.tabAll' },
  { id: 'new', labelKey: 'orders.tabNew' },
  { id: 'accepted', labelKey: 'orders.tabAccepted' },
  { id: 'cancelled', labelKey: 'orders.tabCancelled' },
]

function statusColor(status: string): string {
  if (status === 'Bekor qilingan' || status === 'Rad etildi') return 'var(--danger)'
  if (status === 'Yetkazilmoqda') return 'var(--warning)'
  if (status === 'Yetkazildi') return 'var(--success)'
  if (status === 'Qabul qilindi') return 'var(--info)'
  return 'var(--brand)'
}

type Props = {
  orders: Order[]
  authReady: boolean
  isAuthenticated: boolean
  cartCount: number
  onSearch: () => void
  onOpenCart: () => void
  onGoToCatalog: () => void
  onNotify: (message: string) => void
}

/** Mijoz faqat shu statuslardagi buyurtmani bekor qila oladi. */
const CANCELLABLE: OrderStatus[] = ['Yangi', 'Qabul qilindi']

export function OrdersPage({
  orders, authReady, isAuthenticated, cartCount, onSearch, onOpenCart, onGoToCatalog, onNotify,
}: Props) {
  const t = useT()
  const [active, setActive] = useState('all')
  const [newest, setNewest] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [cancellingId, setCancellingId] = useState<string | null>(null)

  const handleCancel = async (orderId: string) => {
    if (cancellingId) return
    if (!window.confirm(t('orders.cancelConfirm'))) return

    setCancellingId(orderId)
    try {
      await apiPost('/api/order-cancel', { orderId })
      hapticSuccess()
      onNotify(t('orders.cancelled'))
    } catch (error) {
      hapticError()
      onNotify(error instanceof ApiError ? error.message : t('reviews.error'))
    } finally {
      setCancellingId(null)
    }
  }

  const filtered = useMemo(() => {
    if (active === 'all') return orders
    if (active === 'cancelled') {
      return orders.filter((o) => o.status === 'Bekor qilingan' || o.status === 'Rad etildi')
    }
    if (active === 'new') return orders.filter((o) => o.status === 'Yangi')
    return orders.filter(
      (o) => o.status === 'Qabul qilindi' || o.status === 'Yetkazilmoqda' || o.status === 'Yetkazildi',
    )
  }, [active, orders])

  const shown = newest ? filtered : [...filtered].reverse()

  const getPayInfo = (order: Order) => {
    if (order.paymentMethod !== 'Karta') return null
    const s = order.paymentStatus
    if (s === 'Tolangan') return { color: 'var(--success)', bg: 'var(--success-soft)', needsAction: false }
    if (s === 'Rad etildi') return { color: 'var(--danger)', bg: 'var(--danger-soft)', needsAction: true, rejected: true }
    return { color: 'var(--warning)', bg: 'var(--warning-soft)', needsAction: true, rejected: false }
  }

  const translateStatus = (status: OrderStatus) => t(`status.${status}` as TranslationKey)

  return (
    <>
      <PageHeader title={t('orders.title')} onSearch={onSearch} onCart={onOpenCart} cartCount={cartCount} />

      {/* Tablar */}
      <div
        className="mt-6 flex gap-6 overflow-x-auto border-b px-5 sm:px-10 scrollbar-none"
        style={{ borderColor: 'var(--line)' }}
      >
        {TABS.map(({ id, labelKey }) => (
          <button
            onClick={() => setActive(id)}
            key={id}
            className={'tab whitespace-nowrap ' + (active === id ? 'active' : '')}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      <section className="flex items-center justify-end px-5 pt-5 sm:px-10">
        <button onClick={() => setNewest((v) => !v)} className="filter-button">
          <SlidersHorizontal size={17} />
          <span>{newest ? t('orders.newest') : t('orders.oldest')}</span>
          <ChevronDown size={17} className={`transition-transform ${!newest ? 'rotate-180' : ''}`} />
        </button>
      </section>

      <section className="space-y-4 px-5 pb-32 pt-5 sm:px-10">
        {shown.map((order, i) => {
          const payInfo = getPayInfo(order)
          const isExpanded = expandedId === order.id

          return (
            <div key={order.id} className="order-card flex-col gap-3" style={{ animationDelay: `${Math.min(i, 6) * 0.06}s` }}>
              <div className="flex cursor-pointer flex-col gap-3" onClick={() => setExpandedId(isExpanded ? null : order.id)}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--faint)' }}>
                    {formatOrderDate(order.createdAt) || order.date}
                  </p>
                  <div className="flex items-center gap-1.5">
                    {payInfo && !payInfo.needsAction && (
                      <span
                        className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                        style={{ background: payInfo.bg, color: payInfo.color }}
                      >
                        {t('orders.paid')}
                      </span>
                    )}
                    <span
                      className="text-[11px] font-bold uppercase tracking-wider"
                      style={{ color: statusColor(order.status) }}
                    >
                      {translateStatus(order.status)}
                    </span>
                  </div>
                </div>

                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-[15px] font-extrabold leading-tight" style={{ color: 'var(--ink)' }}>
                      {order.products.map((p) => p.product.name).join(', ')}
                    </h3>
                    <p className="mt-0.5 text-[11px] font-semibold" style={{ color: 'var(--muted)' }}>
                      {t('orders.itemCount', { count: order.products.length })}
                    </p>
                  </div>
                  <p className="shrink-0 text-[15px] font-extrabold" style={{ color: 'var(--ink)' }}>
                    {formatPrice(order.total)}
                  </p>
                </div>

                <div
                  className="flex items-center justify-between border-t pt-2.5"
                  style={{ borderColor: 'var(--line-soft)' }}
                >
                  <p className="text-[11px] font-bold" style={{ color: 'var(--faint)' }}>{order.orderNumber}</p>
                  <div className="flex items-center text-xs font-bold" style={{ color: 'var(--brand)' }}>
                    {isExpanded ? t('orders.hide') : t('orders.details')}
                    <ChevronDown size={14} className={`ml-1 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </div>
                </div>
              </div>

              {isExpanded && (
                <div
                  className="space-y-2 border-t pt-3"
                  style={{ borderColor: 'var(--line)', animation: 'fadeIn 0.25s ease' }}
                >
                  {order.products.map((item, idx) => (
                    <div key={item.cartKey ?? idx} className="flex items-center gap-3">
                      <img
                        src={item.product.images?.[0] ? getImageUrl(item.product.images[0]) : ''}
                        alt={item.product.name}
                        loading="lazy"
                        className="size-12 rounded-lg border object-contain p-1"
                        style={{ borderColor: 'var(--line)', background: 'var(--surface-2)' }}
                      />
                      <div className="min-w-0 text-sm">
                        <p className="truncate font-bold" style={{ color: 'var(--ink)' }}>{item.product.name}</p>
                        <p className="text-[11px] font-medium" style={{ color: 'var(--muted)' }}>
                          {item.quantity} {t('common.pcs')}
                          {item.size && ` · ${t('cart.size')}: ${item.size}`}
                          {item.color && ` · ${t('cart.color')}: ${item.color}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {CANCELLABLE.includes(order.status) && (
                <button
                  onClick={() => handleCancel(order.id)}
                  disabled={cancellingId === order.id}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl py-3 text-sm font-bold transition active:scale-95 disabled:opacity-60"
                  style={{
                    background: 'var(--surface-2)',
                    color: 'var(--danger)',
                    border: '1px solid var(--line)',
                  }}
                >
                  {cancellingId === order.id ? (
                    <><Loader2 size={15} className="animate-spin" />{t('orders.cancelling')}</>
                  ) : (
                    <><X size={15} />{t('orders.cancel')}</>
                  )}
                </button>
              )}

              {payInfo?.needsAction && (
                <button
                  onClick={() => openBotDeepLink(BRAND.botUsername, `receipt_${order.id}`)}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl py-3 text-sm font-bold transition active:scale-95"
                  style={{
                    background: payInfo.bg,
                    color: payInfo.color,
                    border: `1px solid ${payInfo.color}`,
                  }}
                >
                  <ExternalLink size={15} />
                  {payInfo.rejected ? t('orders.resendReceipt') : t('orders.sendReceipt')}
                </button>
              )}
            </div>
          )
        })}

        {!authReady && (
          <div className="flex flex-col items-center py-20 text-center">
            <div
              className="size-8 animate-spin rounded-full border-4"
              style={{ borderColor: 'var(--brand-soft)', borderTopColor: 'var(--brand)' }}
            />
            <p className="mt-4 text-sm" style={{ color: 'var(--muted)' }}>{t('common.loading')}</p>
          </div>
        )}

        {authReady && !isAuthenticated && (
          <div className="flex flex-col items-center py-20 text-center" style={{ animation: 'fadeInUp 0.4s ease' }}>
            <span
              className="grid size-20 place-items-center rounded-full"
              style={{ background: 'var(--warning-soft)', color: 'var(--warning)' }}
            >
              <ShoppingBag size={34} />
            </span>
            <p className="mt-5 text-lg font-bold" style={{ color: 'var(--ink-2)' }}>{t('orders.authFailed')}</p>
            <p className="mt-2 max-w-[280px] text-sm" style={{ color: 'var(--muted)' }}>
              {t('orders.authFailedText')}
            </p>
          </div>
        )}

        {authReady && isAuthenticated && !shown.length && (
          <div className="flex flex-col items-center py-20 text-center" style={{ animation: 'fadeInUp 0.4s ease' }}>
            <span
              className="grid size-20 place-items-center rounded-full"
              style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
            >
              <ShoppingBag size={34} />
            </span>
            <p className="mt-5 text-lg font-bold" style={{ color: 'var(--ink-2)' }}>
              {orders.length === 0 ? t('orders.empty') : t('orders.emptyFilter')}
            </p>
            <p className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>
              {orders.length === 0 ? t('orders.emptyText') : t('orders.emptyFilterText')}
            </p>
            {orders.length === 0 && (
              <button onClick={onGoToCatalog} className="btn-ghost mt-6 px-6 py-3">
                {t('cart.goToCatalog')}
              </button>
            )}
          </div>
        )}
      </section>
    </>
  )
}
