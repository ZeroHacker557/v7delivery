import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight, Bell, CircleHelp, CupSoda, Heart, Leaf, Search,
  ShieldCheck, Truck,
} from 'lucide-react'
import heroCan from '../images/hero-can.webp'
import { BrandLogo } from '../components/brand/BrandLogo'
import { ProductCard } from '../components/product/ProductCard'
import { ProductRowSkeleton } from '../components/ui/ProductCardSkeleton'
import { CartButton } from '../components/ui/CartButton'
import { IconButton } from '../components/ui/IconButton'
import { categoryIcon } from '../utils/category-icons'
import { useT, type TranslationKey } from '../i18n'
import type { AppPage, Category, Product, ProductActions } from '../types/domain'

const benefits: [LucideIcon, TranslationKey, TranslationKey][] = [
  [Truck, 'benefit.delivery', 'benefit.deliverySub'],
  [ShieldCheck, 'benefit.payment', 'benefit.paymentSub'],
  [CircleHelp, 'benefit.support', 'benefit.supportSub'],
  [Leaf, 'benefit.natural', 'benefit.naturalSub'],
]

type Props = ProductActions & {
  products: Product[]
  categories: Category[]
  loading: boolean
  cartCount: number
  onSearch: () => void
  onNavigate: (page: AppPage) => void
  onOpenCategory: (category: string) => void
  onOpenCart: () => void
  unreadNotificationsCount: number
  onNotify: (message: string) => void
}

export function HomePage({
  products, categories, loading, cartCount, onSearch, onNavigate,
  onOpenCategory, onOpenCart, unreadNotificationsCount, onNotify, ...productActions
}: Props) {
  const t = useT()

  return (
    <>
      {/* Header */}
      <header className="flex items-center justify-between px-5 pt-7 sm:px-10">
        <BrandLogo size={44} />
        <div className="flex items-center gap-1">
          <IconButton label={t('notifications.title')} onClick={() => onNavigate('notifications')}>
            <span className="relative">
              <Bell />
              {unreadNotificationsCount > 0 && (
                <span
                  className="absolute right-0 top-0 size-2.5 rounded-full border-2"
                  style={{ background: 'var(--danger)', borderColor: 'var(--surface)' }}
                />
              )}
            </span>
          </IconButton>
          <IconButton label={t('favorites.title')} onClick={() => onNavigate('favorites')}>
            <Heart />
          </IconButton>
          <CartButton count={cartCount} onClick={onOpenCart} />
        </div>
      </header>

      {/* Search */}
      <section className="px-5 pt-6 sm:px-10">
        <button
          onClick={onSearch}
          className="flex h-13 w-full items-center gap-3 rounded-2xl border px-4 py-3.5 text-left transition"
          style={{ borderColor: 'var(--line)', color: 'var(--faint)', background: 'var(--surface-2)' }}
        >
          <Search className="shrink-0" size={20} />
          <span className="truncate text-sm">{t('home.searchPlaceholder')}</span>
        </button>
      </section>

      {/* Hero — Lemon Mint bankasi to'q yashil sahnada */}
      <section className="mx-5 mt-6 sm:mx-10">
        <div className="hero-banner">
          <div className="relative min-h-[260px] p-6 sm:min-h-[340px] sm:p-9">
            <span className="hero-glow" aria-hidden="true" />

            <div className="relative z-10 max-w-[58%] sm:max-w-[380px]">
              <span
                className="inline-block rounded-full px-3 py-1 text-xs font-bold"
                style={{ background: '#ffffff', color: 'var(--brand-strong)' }}
              >
                {t('home.heroBadge')}
              </span>
              <h2
                className="wordmark mt-4 text-[1.5rem] leading-[1.15] sm:text-[2.4rem]"
                style={{ color: '#ffffff', textWrap: 'balance' }}
              >
                {t('home.heroTitle')}
              </h2>
              <p className="mt-3 text-sm sm:text-base" style={{ color: 'rgb(255 255 255 / 0.78)' }}>
                {t('home.heroSubtitle')}
              </p>
              <button
                onClick={() => onNavigate('catalog')}
                className="mt-5 flex w-fit items-center gap-2 whitespace-nowrap rounded-full px-5 py-3 font-bold transition active:scale-[0.98]"
                style={{ background: '#ffffff', color: 'var(--brand-strong)' }}
              >
                {t('home.heroCta')} <ArrowRight size={18} />
              </button>
            </div>

            <img
              className="pointer-events-none absolute top-1/2 right-[-4%] h-[112%] w-[52%] -translate-y-1/2 object-contain object-center sm:right-2 sm:h-[118%] sm:w-[46%]"
              src={heroCan}
              alt=""
              aria-hidden="true"
              decoding="async"
              fetchPriority="high"
            />
          </div>
        </div>
      </section>

      {/* Kategoriyalar — bazadan, bosilganda katalog filtrlanadi */}
      {categories.length > 0 && (
        <section className="mt-6">
          <div className="category-strip scrollbar-none">
            {categories.map((category) => {
              const Icon = categoryIcon(category.icon, category.name)
              return (
                <button
                  onClick={() => onOpenCategory(category.name)}
                  key={category.id}
                  className="category-card"
                >
                  <span className="category-icon-wrap">
                    <Icon size={22} />
                  </span>
                  <span className="line-clamp-1">{category.name}</span>
                </button>
              )
            })}
          </div>
        </section>
      )}

      {/* Afzalliklar */}
      <section
        className="mx-5 mt-6 grid grid-cols-2 rounded-2xl border p-3 sm:mx-10 sm:grid-cols-4"
        style={{ borderColor: 'var(--line)', background: 'var(--surface)' }}
      >
        {benefits.map(([Icon, titleKey, subKey]) => (
          <button
            onClick={() => onNotify(`${t(titleKey)}: ${t(subKey)}`)}
            key={titleKey}
            className="benefit-item"
          >
            <span
              className="grid size-9 shrink-0 place-items-center rounded-full"
              style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
            >
              <Icon size={19} />
            </span>
            <p className="text-[11px] font-bold leading-tight sm:text-xs" style={{ color: 'var(--ink)' }}>
              {t(titleKey)}
              <small className="mt-0.5 block font-normal" style={{ color: 'var(--muted)' }}>
                {t(subKey)}
              </small>
            </p>
          </button>
        ))}
      </section>

      {/* Mashhur mahsulotlar */}
      <section className="px-5 pb-32 pt-8 sm:px-10">
        <div className="flex items-center justify-between">
          <h2 className="section-title">{t('home.popular')}</h2>
          <button
            onClick={() => onNavigate('catalog')}
            className="text-sm font-bold transition hover:opacity-80"
            style={{ color: 'var(--brand)' }}
          >
            {t('home.seeAll')}
          </button>
        </div>

        {loading ? (
          <ProductRowSkeleton />
        ) : products.length > 0 ? (
          <div className="mt-5 flex gap-4 overflow-x-auto pb-2 scrollbar-none">
            {products.slice(0, 8).map((product) => (
              <ProductCard key={product.id} product={product} compact {...productActions} />
            ))}
          </div>
        ) : (
          <div
            className="mt-8 rounded-2xl border border-dashed p-10 text-center"
            style={{ borderColor: 'var(--line)' }}
          >
            <span
              className="mx-auto grid size-16 place-items-center rounded-full"
              style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
            >
              <CupSoda size={30} />
            </span>
            <p className="mt-4 font-bold" style={{ color: 'var(--ink-2)' }}>{t('home.emptyTitle')}</p>
            <p className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>{t('home.emptyText')}</p>
          </div>
        )}
      </section>
    </>
  )
}
