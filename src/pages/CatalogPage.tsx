import { useMemo, useState } from 'react'
import { Check, ChevronDown, Grid2X2, Package, SlidersHorizontal, X } from 'lucide-react'
import { formatPrice } from '../data'
import { PageHeader } from '../components/layout/PageHeader'
import { ProductCard } from '../components/product/ProductCard'
import { ProductGridSkeleton } from '../components/ui/ProductCardSkeleton'
import { categoryIcon } from '../utils/category-icons'
import { useT } from '../i18n'
import type { Category, Product, ProductActions } from '../types/domain'

/** Bir sahifada nechta mahsulot ko'rsatiladi (4-band). */
const PAGE_SIZE = 12

type Props = ProductActions & {
  products: Product[]
  categories: Category[]
  loading: boolean
  cartCount: number
  /** Bosh sahifadan kelgan kategoriya filtri. */
  initialCategory?: string | null
  onSearch: () => void
  onOpenCart: () => void
}

/** Mahsulotdagi ranglar bitta qatorda saqlanadi: "Qora, Oq, Qizil". */
function productColors(product: Product): string[] {
  if (product.colors?.length) return product.colors
  if (!product.color) return []
  return product.color.split(',').map((c) => c.trim()).filter(Boolean)
}

export function CatalogPage({
  products, categories, loading, cartCount, initialCategory, onSearch, onOpenCart, ...actions
}: Props) {
  const t = useT()
  const ALL = t('common.all')

  const [active, setActive] = useState(initialCategory || ALL)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [sortAscending, setSortAscending] = useState(true)
  const [visible, setVisible] = useState(PAGE_SIZE)

  // Filtrlar (2-band)
  const [priceFrom, setPriceFrom] = useState('')
  const [priceTo, setPriceTo] = useState('')
  const [size, setSize] = useState<string | null>(null)
  const [color, setColor] = useState<string | null>(null)
  const [inStockOnly, setInStockOnly] = useState(false)

  const displayCategories = useMemo(
    () => [{ id: -1, name: ALL, icon: 'all' }, ...categories],
    [categories, ALL],
  )

  // Mavjud o'lcham va ranglar — faqat haqiqatan bor variantlar ko'rsatiladi
  const { allSizes, allColors, maxPrice } = useMemo(() => {
    const sizes = new Set<string>()
    const colors = new Set<string>()
    let max = 0
    products.forEach((p) => {
      p.sizes?.forEach((s) => sizes.add(s))
      productColors(p).forEach((c) => colors.add(c))
      if (p.price > max) max = p.price
    })
    return {
      allSizes: [...sizes].sort(),
      allColors: [...colors].sort(),
      maxPrice: max,
    }
  }, [products])

  const activeFilterCount =
    (priceFrom ? 1 : 0) + (priceTo ? 1 : 0) + (size ? 1 : 0) + (color ? 1 : 0) + (inStockOnly ? 1 : 0)

  const shown = useMemo(() => {
    const from = Number(priceFrom) || 0
    const to = Number(priceTo) || Infinity

    const filtered = products.filter((p) => {
      if (active !== ALL && p.category !== active) return false
      if (p.price < from || p.price > to) return false
      if (size && !p.sizes?.includes(size)) return false
      if (color && !productColors(p).includes(color)) return false
      if (inStockOnly && p.stock === 0) return false
      return true
    })

    return [...filtered].sort((a, b) => (sortAscending ? a.price - b.price : b.price - a.price))
  }, [products, active, ALL, priceFrom, priceTo, size, color, inStockOnly, sortAscending])

  // Filtr o'zgarsa boshidan ko'rsatamiz
  const pageKey = `${active}|${priceFrom}|${priceTo}|${size}|${color}|${inStockOnly}|${sortAscending}`
  const [lastKey, setLastKey] = useState(pageKey)
  if (pageKey !== lastKey) {
    setLastKey(pageKey)
    setVisible(PAGE_SIZE)
  }

  const page = shown.slice(0, visible)
  const hasMore = shown.length > visible

  const resetFilters = () => {
    setPriceFrom('')
    setPriceTo('')
    setSize(null)
    setColor(null)
    setInStockOnly(false)
  }

  return (
    <>
      <PageHeader title={t('catalog.title')} onSearch={onSearch} onCart={onOpenCart} cartCount={cartCount} />

      {/* Kategoriyalar */}
      <section className="category-strip scrollbar-none mt-6">
        {displayCategories.map((category) => {
          const Icon = category.name === ALL ? Grid2X2 : categoryIcon(category.icon, category.name)
          return (
            <button
              onClick={() => setActive(category.name)}
              key={category.id}
              className={'catalog-category ' + (active === category.name ? 'active' : '')}
            >
              <Icon size={21} />
              <span className="line-clamp-1">{category.name}</span>
            </button>
          )
        })}
      </section>

      {/* Filtr va saralash */}
      <section className="flex items-center justify-between gap-3 px-5 pt-5 sm:px-10">
        <button
          onClick={() => setFiltersOpen((o) => !o)}
          className="filter-button"
          style={
            filtersOpen || activeFilterCount
              ? { borderColor: 'var(--brand)', background: 'var(--brand-soft)', color: 'var(--brand)' }
              : undefined
          }
        >
          <SlidersHorizontal size={18} />
          <span>{t('catalog.filters')}</span>
          {activeFilterCount > 0 && (
            <span
              className="grid size-5 place-items-center rounded-full text-[10px] font-bold"
              style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}
            >
              {activeFilterCount}
            </span>
          )}
        </button>
        <button onClick={() => setSortAscending((v) => !v)} className="filter-button">
          <span>{sortAscending ? t('catalog.sortCheap') : t('catalog.sortExpensive')}</span>
          <ChevronDown
            size={17}
            className={`transition-transform duration-300 ${!sortAscending ? 'rotate-180' : ''}`}
          />
        </button>
      </section>

      {/* Filtrlar paneli */}
      {filtersOpen && (
        <section
          className="mx-5 mt-4 rounded-2xl border p-4 sm:mx-10"
          style={{
            borderColor: 'var(--line)',
            background: 'var(--surface)',
            animation: 'fadeInUp 0.25s ease',
          }}
        >
          <div className="mb-4 flex items-center justify-between">
            <b style={{ color: 'var(--ink)' }}>{t('catalog.filters')}</b>
            <button
              onClick={() => setFiltersOpen(false)}
              className="grid size-7 place-items-center rounded-lg"
              style={{ color: 'var(--muted)' }}
              aria-label={t('common.close')}
            >
              <X size={16} />
            </button>
          </div>

          {/* Narx oralig'i */}
          <div className="mb-4">
            <label className="field-label">{t('catalog.priceRange')}</label>
            <div className="flex items-center gap-2">
              <div className="field h-11 flex-1 py-0">
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={priceFrom}
                  onChange={(e) => setPriceFrom(e.target.value)}
                  placeholder={t('catalog.priceFrom')}
                  className="text-sm"
                />
              </div>
              <span style={{ color: 'var(--faint)' }}>—</span>
              <div className="field h-11 flex-1 py-0">
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={priceTo}
                  onChange={(e) => setPriceTo(e.target.value)}
                  placeholder={maxPrice ? formatPrice(maxPrice) : t('catalog.priceTo')}
                  className="text-sm"
                />
              </div>
            </div>
          </div>

          {/* Hajm */}
          {allSizes.length > 0 && (
            <div className="mb-4">
              <label className="field-label">{t('catalog.size')}</label>
              <div className="flex flex-wrap gap-2">
                {allSizes.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSize(size === s ? null : s)}
                    className="rounded-xl border px-3 py-2 text-sm font-bold transition"
                    style={{
                      borderColor: size === s ? 'var(--brand)' : 'var(--line)',
                      background: size === s ? 'var(--brand-soft)' : 'var(--surface)',
                      color: size === s ? 'var(--brand)' : 'var(--ink)',
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Ta'm */}
          {allColors.length > 0 && (
            <div className="mb-4">
              <label className="field-label">{t('catalog.color')}</label>
              <div className="flex flex-wrap gap-2">
                {allColors.map((c) => (
                  <button
                    key={c}
                    onClick={() => setColor(color === c ? null : c)}
                    className="rounded-xl border px-3 py-2 text-sm font-bold transition"
                    style={{
                      borderColor: color === c ? 'var(--brand)' : 'var(--line)',
                      background: color === c ? 'var(--brand-soft)' : 'var(--surface)',
                      color: color === c ? 'var(--brand)' : 'var(--ink)',
                    }}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Faqat sotuvdagilar */}
          <button
            onClick={() => setInStockOnly((v) => !v)}
            className="mb-4 flex w-full items-center gap-3 rounded-xl border p-3 text-left transition"
            style={{
              borderColor: inStockOnly ? 'var(--brand)' : 'var(--line)',
              background: inStockOnly ? 'var(--brand-soft)' : 'var(--surface)',
            }}
          >
            <span
              className="grid size-5 shrink-0 place-items-center rounded-md border"
              style={{
                borderColor: inStockOnly ? 'var(--brand)' : 'var(--line)',
                background: inStockOnly ? 'var(--brand)' : 'transparent',
                color: 'var(--brand-ink)',
              }}
            >
              {inStockOnly && <Check size={14} />}
            </span>
            <span className="text-sm font-bold" style={{ color: inStockOnly ? 'var(--brand)' : 'var(--ink)' }}>
              {t('catalog.inStockOnly')}
            </span>
          </button>

          <div className="flex gap-2">
            <button onClick={resetFilters} className="btn-ghost flex-1 py-3 text-sm">
              {t('catalog.reset')}
            </button>
            <button onClick={() => setFiltersOpen(false)} className="btn-primary flex-1 py-3 text-sm">
              {t('catalog.apply')}
            </button>
          </div>
        </section>
      )}

      {/* Mahsulotlar */}
      <section className="px-5 pb-32 pt-6 sm:px-10">
        <p style={{ color: 'var(--muted)' }}>{t('catalog.total', { count: shown.length })}</p>

        {loading ? (
          <ProductGridSkeleton />
        ) : page.length > 0 ? (
          <>
            <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {page.map((product) => (
                <ProductCard key={product.id} product={product} {...actions} />
              ))}
            </div>

            {hasMore && (
              <div className="mt-8 flex flex-col items-center gap-3">
                <p className="text-xs font-bold" style={{ color: 'var(--faint)' }}>
                  {t('catalog.showing', { shown: page.length, total: shown.length })}
                </p>
                <button
                  onClick={() => setVisible((v) => v + PAGE_SIZE)}
                  className="btn-ghost px-8 py-3"
                >
                  {t('catalog.loadMore')}
                </button>
              </div>
            )}
          </>
        ) : (
          <div
            className="mt-8 rounded-2xl border border-dashed p-12 text-center"
            style={{ borderColor: 'var(--line)' }}
          >
            <span
              className="mx-auto grid size-16 place-items-center rounded-full"
              style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
            >
              <Package size={30} />
            </span>
            <p className="mt-4 font-bold" style={{ color: 'var(--ink-2)' }}>
              {products.length === 0 ? t('home.emptyTitle') : t('catalog.emptyCategory')}
            </p>
            <p className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>
              {products.length === 0 ? t('home.emptyText') : t('catalog.emptyCategoryText')}
            </p>
            {products.length > 0 && (activeFilterCount > 0 || active !== ALL) && (
              <button
                onClick={() => { resetFilters(); setActive(ALL) }}
                className="btn-ghost mx-auto mt-5 px-5 py-2.5 text-sm"
              >
                {t('catalog.reset')}
              </button>
            )}
          </div>
        )}
      </section>
    </>
  )
}
