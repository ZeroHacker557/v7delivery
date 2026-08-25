import markWhite from '../../images/v7-mark-white.png'

type Props = {
  /** Belgi o'lchami (px). Yozuv shunga nisbatan masshtablanadi. */
  size?: number
  /** Yozuvsiz — faqat belgi (kichik joylar uchun). */
  markOnly?: boolean
  className?: string
}

/**
 * V7™ logotipi.
 *
 * Belgi doimo yashil plitka ustidagi OQ variant — logotipning yashil
 * varianti qorong'i temada fon bilan qo'shilib ketadi, oq plitka esa
 * yorug' temada yo'qoladi. Plitka ikkalasida ham bir xil ko'rinadi va
 * favicon bilan aynan mos tushadi.
 */
export function BrandLogo({ size = 44, markOnly = false, className = '' }: Props) {
  return (
    <span className={'flex items-center gap-2.5 ' + className}>
      <span
        className="grid shrink-0 place-items-center"
        style={{
          width: size,
          height: size,
          borderRadius: size * 0.28,
          background: 'var(--brand)',
          boxShadow: 'var(--shadow-brand)',
        }}
      >
        <img
          src={markWhite}
          alt="V7"
          style={{ width: size * 0.62, height: 'auto' }}
          decoding="async"
        />
      </span>

      {!markOnly && (
        <span className="min-w-0 leading-none">
          <b
            className="wordmark block"
            style={{ fontSize: size * 0.6, color: 'var(--ink)' }}
          >
            V7<sup style={{ fontSize: '0.4em', verticalAlign: 'super' }}>™</sup>
          </b>
          <small
            className="mt-1 block font-bold uppercase"
            style={{
              fontSize: Math.max(7, size * 0.17),
              letterSpacing: '0.14em',
              color: 'var(--brand)',
            }}
          >
            Vitamin Sparkling
          </small>
        </span>
      )}
    </span>
  )
}
