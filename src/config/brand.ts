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
  botUsername: 'ecommercy_test_bot',

  /** Mijozlar xizmati. */
  phone: '+998 78 777 07 07',
  phoneHref: 'tel:+998787770707',
  email: 'info@v7.uz',
  telegram: '@v7uz',
  telegramHref: 'https://t.me/v7uz',

  /** Ish vaqti va manzil — bot javoblarida ham ishlatiladi. */
  city: "Toshkent, O'zbekiston",
  workHours: '09:00 — 20:00',
} as const

export const BOT_URL = `https://t.me/${BRAND.botUsername}`
