/**
 * V7™ brend va kompaniya ma'lumotlari — bitta manba.
 *
 * Bot username, domen va aloqa raqamlari shu yerda turadi; ilovaning
 * qolgan qismi faqat shu konstantalarga murojaat qiladi. Yangi bot
 * tokeni / domen kelganda o'zgartiriladigan yagona fayl (bot tomonida
 * esa bot/config.py).
 */
export const BRAND = {
  name: 'V7',
  legalName: 'V7™',
  tagline: 'Vitamin Sparkling Drink',

  /** Telegram bot — mini app shu bot ichida ochiladi. */
  botUsername: 'v7buyurtma_bot',

  /** Mijozlar xizmati. */
  phone: '+998 95 177 88 82',
  phoneHref: 'tel:+998951778882',
  email: 'abubakrfrontend@gmail.com',
  telegram: '@v7uzbekistan',
  telegramHref: 'https://t.me/v7uzbekistan',

  /** Ish vaqti va manzil — bot javoblarida ham ishlatiladi. */
  city: "Toshkent, O'zbekiston",
  workHours: '09:00 — 20:00',
} as const

/**
 * Ilovani ishlab chiqqan dasturchi — "Yordam" sahifasidagi alohida blok.
 * Texnik savollar V7 mijozlar xizmatiga emas, shu manzillarga tushadi.
 */
export const DEVELOPER = {
  name: 'Abubakr.A',
  phone: '+998 97 400 98 77',
  phoneHref: 'tel:+998974009877',
  telegram: '@for_name',
  telegramHref: 'https://t.me/for_name',
  email: 'abubakrfrontend@gmail.com',
} as const

export const BOT_URL = `https://t.me/${BRAND.botUsername}`
