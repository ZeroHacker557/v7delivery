import { useEffect, useState } from 'react'
import { ChevronLeft, MapPin, Plus, Trash2 } from 'lucide-react'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'
import { updateUserProfile } from '../lib/firebase'
import { auth } from '../lib/auth'
import { hapticFeedback, hapticSuccess } from '../utils/telegram'
import { useT } from '../i18n'
import type { Address, UserProfile } from '../types/domain'

// Leaflet standart ikonkasi bundler bilan ishlamaydi — qo'lda beramiz
L.Marker.prototype.options.icon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
})

const TASHKENT = { lat: 41.2995, lng: 69.2401 }

function MapUpdater({ center }: { center: { lat: number; lng: number } }) {
  const map = useMap()
  useEffect(() => {
    map.flyTo([center.lat, center.lng], map.getZoom())
  }, [center, map])
  return null
}

function MapEvents({ onPick }: { onPick: (p: { lat: number; lng: number }) => void }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng })
      hapticFeedback('light')
    },
  })
  return null
}

type Props = {
  profile: UserProfile | null
  onBack: () => void
  onNotify: (msg: string) => void
}

export function AddressesPage({ profile, onBack, onNotify }: Props) {
  const t = useT()
  const addresses = profile?.addresses || []

  const [isAdding, setIsAdding] = useState(false)
  const [loading, setLoading] = useState(false)
  const [newName, setNewName] = useState('')
  const [newFullAddress, setNewFullAddress] = useState('')
  const [mapCenter, setMapCenter] = useState(TASHKENT)
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null)

  const handleCurrentLocation = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = { lat: pos.coords.latitude, lng: pos.coords.longitude }
        setMapCenter(coords)
        setLocation(coords)
        hapticFeedback('medium')
      },
      () => onNotify(t('address.locationFailed')),
    )
  }

  const handleSaveAddress = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim() || !newFullAddress.trim() || !location) {
      onNotify(t('address.fillAll'))
      return
    }

    const uid = auth.currentUser?.uid
    if (!uid) {
      // Firebase seansi yo'q. Ilgari bu yerda jim `return` turardi —
      // tugma bosilardi-yu hech narsa bo'lmasdi va sabab ko'rinmasdi.
      onNotify(t('error.notSignedIn'))
      return
    }
    if (!profile) {
      // Profil hali o'qilmagan: hozir yozsak mavjud manzillar o'chib ketadi
      onNotify(t('common.loading'))
      return
    }

    setLoading(true)
    try {
      const newAddress: Address = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: newName.trim(),
        address: newFullAddress.trim(),
        location,
      }
      await updateUserProfile(Number(uid), { addresses: [...addresses, newAddress] })
      setIsAdding(false)
      setNewName('')
      setNewFullAddress('')
      setLocation(null)
      hapticSuccess()
      onNotify(t('address.saved'))
    } catch (error) {
      console.error('[Manzil] saqlanmadi:', error)
      onNotify(t('error.saveFailed'))
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAddress = async (id: string) => {
    const uid = auth.currentUser?.uid
    if (!uid) {
      onNotify(t('error.notSignedIn'))
      return
    }
    try {
      await updateUserProfile(Number(uid), { addresses: addresses.filter((a) => a.id !== id) })
      hapticFeedback('light')
      onNotify(t('address.deleted'))
    } catch (error) {
      console.error('[Manzil] o\'chirilmadi:', error)
      onNotify(t('error.saveFailed'))
    }
  }

  return (
    <>
      <header className="flex items-center gap-3 px-5 pt-8 sm:px-10">
        <button
          onClick={() => (isAdding ? setIsAdding(false) : onBack())}
          className="icon-button"
          aria-label={t('common.back')}
        >
          <ChevronLeft size={22} />
        </button>
        <h1 className="text-2xl font-extrabold" style={{ color: 'var(--ink)' }}>
          {isAdding ? t('address.new') : t('address.title')}
        </h1>
      </header>

      {isAdding ? (
        <form onSubmit={handleSaveAddress} className="px-5 pb-32 pt-6 sm:px-10 page-animate">
          <div className="space-y-5">
            <div>
              <label className="field-label">
                {t('address.name')} <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <div className="field">
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('address.namePlaceholder')}
                  required
                />
              </div>
            </div>

            <div>
              <label className="field-label">
                {t('address.full')} <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <div className="field">
                <input
                  value={newFullAddress}
                  onChange={(e) => setNewFullAddress(e.target.value)}
                  placeholder={t('address.fullPlaceholder')}
                  required
                />
              </div>
            </div>

            <div>
              <label className="field-label">
                {t('address.pickOnMap')} <span style={{ color: 'var(--danger)' }}>*</span>
              </label>
              <div
                className="relative mt-2 h-[280px] w-full overflow-hidden rounded-2xl border"
                style={{ borderColor: 'var(--line)' }}
              >
                <MapContainer center={[mapCenter.lat, mapCenter.lng]} zoom={12} style={{ height: '100%', width: '100%', zIndex: 1 }}>
                  <MapUpdater center={mapCenter} />
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
                  {location && <Marker position={location} />}
                  <MapEvents onPick={setLocation} />
                </MapContainer>

                <button
                  type="button"
                  onClick={handleCurrentLocation}
                  className="absolute bottom-4 right-4 z-[400] grid size-12 place-items-center rounded-xl transition active:scale-95"
                  style={{ background: 'var(--surface)', color: 'var(--brand)', boxShadow: 'var(--shadow-md)' }}
                  aria-label={t('address.pickOnMap')}
                >
                  <MapPin size={22} />
                </button>
              </div>
              <p className="mt-2 text-center text-xs" style={{ color: 'var(--faint)' }}>{t('address.mapHint')}</p>
            </div>
          </div>

          <button type="submit" disabled={loading} className="btn-primary mt-8 w-full py-4">
            {loading ? t('common.saving') : t('common.save')}
          </button>
        </form>
      ) : (
        <div className="px-5 pb-32 pt-6 sm:px-10 page-animate">
          {addresses.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div
                className="mb-4 grid size-16 place-items-center rounded-full"
                style={{ background: 'var(--surface-3)', color: 'var(--muted)' }}
              >
                <MapPin size={26} />
              </div>
              <h3 className="text-lg font-bold" style={{ color: 'var(--ink-2)' }}>{t('address.empty')}</h3>
              <p className="mt-1 max-w-[240px] text-sm" style={{ color: 'var(--muted)' }}>{t('address.emptyText')}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {addresses.map((addr) => (
                <div
                  key={addr.id}
                  className="flex items-center gap-4 rounded-2xl border p-4"
                  style={{ borderColor: 'var(--line)', background: 'var(--surface)' }}
                >
                  <div
                    className="grid size-10 shrink-0 place-items-center rounded-full"
                    style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }}
                  >
                    <MapPin size={19} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="font-bold" style={{ color: 'var(--ink)' }}>{addr.name}</h4>
                    <p className="mt-0.5 truncate text-xs font-medium" style={{ color: 'var(--muted)' }}>{addr.address}</p>
                  </div>
                  <button
                    onClick={() => handleDeleteAddress(addr.id)}
                    className="p-2 transition-colors"
                    style={{ color: 'var(--muted)' }}
                    aria-label={t('common.cancel')}
                  >
                    <Trash2 size={19} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => setIsAdding(true)}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-4 font-bold transition"
            style={{ borderColor: 'var(--brand-line)', background: 'var(--brand-soft)', color: 'var(--brand)' }}
          >
            <Plus size={20} />
            {t('address.add')}
          </button>
        </div>
      )}
    </>
  )
}
