import {
  Apple, Cherry, Citrus, CupSoda, Droplets, GlassWater, Grape, Grid2X2,
  Leaf, Package, Snowflake, Sparkles, Wheat,
  type LucideIcon,
} from 'lucide-react'

/**
 * Kategoriya ikonkasi.
 *
 * Avval bazadagi `icon` maydoniga qaraydi (admin tanlagan), topilmasa
 * nom bo'yicha taxmin qiladi, u ham bo'lmasa umumiy banka ishlatiladi.
 * Ilgari faqat oldindan yozilgan nomlar bilan solishtirilardi, shuning
 * uchun har qanday yangi kategoriya doim quti bo'lib qolardi (F-17).
 *
 * Ro'yxat V7 assortimentiga moslangan: uchta liniya (Vitamin Sparkling,
 * Super Soda, Flavored Malt) va to'qqizta ta'm.
 */
const BY_KEY: Record<string, LucideIcon> = {
  all: Grid2X2,
  soda: CupSoda,
  drink: CupSoda,
  can: CupSoda,
  water: GlassWater,
  suv: GlassWater,
  vitamin: Sparkles,
  sparkling: Sparkles,
  malt: Wheat,
  citrus: Citrus,
  lemon: Citrus,
  limon: Citrus,
  mint: Leaf,
  yalpiz: Leaf,
  apple: Apple,
  olma: Apple,
  grape: Grape,
  berry: Cherry,
  cherry: Cherry,
  pomegranate: Cherry,
  cola: CupSoda,
  diet: Droplets,
  ice: Snowflake,
  box: Package,
}

const BY_NAME: [RegExp, LucideIcon][] = [
  [/vitamin|sparkling|витамин/i, Sparkles],
  [/malt|солод/i, Wheat],
  [/soda|kola|cola|кола|содa|сода/i, CupSoda],
  [/limon|lemon|citrus|лимон|цитрус/i, Citrus],
  [/yalpiz|mint|мят/i, Leaf],
  [/olma|apple|яблок/i, Apple],
  [/anor|pomegranate|chernika|blueberry|гранат|черник|uzum|grape|виноград/i, Cherry],
  [/ananas|pineapple|kolada|colada|ананас|тропик/i, Grape],
  [/diet|shakarsiz|без сахара|zero/i, Droplets],
  [/suv|water|вода/i, GlassWater],
  [/muz|ice|лед|лёд/i, Snowflake],
  [/barcha|hamma|все|all/i, Grid2X2],
]

/**
 * Bot yangi kategoriyaga doim "package" yozadi — bu "tanlanmagan" degani.
 * Shuning uchun uni e'tiborsiz qoldirib, nom bo'yicha aniqlashga o'tamiz.
 */
const UNSET_ICONS = new Set(['', 'package', 'Package'])

export function categoryIcon(icon?: string, name?: string): LucideIcon {
  if (icon && !UNSET_ICONS.has(icon.trim())) {
    const found = BY_KEY[icon.toLowerCase().trim()]
    if (found) return found
  }
  if (name) {
    for (const [pattern, Icon] of BY_NAME) {
      if (pattern.test(name)) return Icon
    }
  }
  return CupSoda
}
