import { useEffect, useMemo, useRef, useState } from 'react'
import { clsx } from 'clsx'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import {
  Activity,
  AlertTriangle,
  Ambulance,
  Building2,
  Car,
  Crosshair,
  FlaskConical,
  HeartPulse,
  Hospital,
  LocateFixed,
  Maximize2,
  MapPin,
  Minimize2,
  Navigation,
  RadioTower,
  Route,
  ShieldAlert,
  Zap,
} from 'lucide-react'

import useDispatchStore from '../../store/dispatchStore'
import { fetchDemandHeatmap, triggerScenario } from '../../services/api'
import Badge from '../ui/Badge'
import Button from '../ui/Button'

const CITY_CENTERS = {
  Delhi: [77.209, 28.6139],
  Mumbai: [72.8777, 19.076],
  Bengaluru: [77.5946, 12.9716],
  Chennai: [80.2707, 13.0827],
  Hyderabad: [78.4867, 17.385],
}
const CITY_NAMES = Object.keys(CITY_CENTERS)

function cityKey(value) {
  return String(value || '').trim().toLowerCase()
}

function sameCity(left, right) {
  const leftKey = cityKey(left)
  const rightKey = cityKey(right)
  return Boolean(leftKey && rightKey && leftKey === rightKey)
}

function inServiceCity(item, city) {
  return !city || sameCity(item?.city, city)
}

function mergeUniqueById(primary, extras) {
  const byId = new Map()
  primary.forEach((item) => {
    if (item?.id) byId.set(item.id, item)
  })
  extras.forEach((item) => {
    if (item?.id) byId.set(item.id, item)
  })
  return Array.from(byId.values())
}

const DARK_RASTER_STYLE = {
  version: 8,
  sources: {
    cartoDark: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    },
  },
  layers: [
    {
      id: 'carto-dark',
      type: 'raster',
      source: 'cartoDark',
      minzoom: 0,
      maxzoom: 20,
    },
  ],
}

const EMPTY_COLLECTION = { type: 'FeatureCollection', features: [] }
const SIMULATION_SCENARIOS = [
  { type: 'cardiac', label: 'Incident', icon: HeartPulse },
  { type: 'traffic', label: 'Traffic', icon: Route },
  { type: 'breakdown', label: 'Breakdown', icon: Car },
  { type: 'overload', label: 'Hospital Full', icon: ShieldAlert },
]

function isJsdom() {
  return typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)
}

function routeFeature(route, source = 'active') {
  if (!route?.coordinates?.length) return null
  return {
    type: 'Feature',
    properties: {
      source,
      ambulance_id: route.ambulance_id,
      eta_minutes: route.eta_minutes,
    },
    geometry: {
      type: 'LineString',
      coordinates: route.coordinates,
    },
  }
}

function featureCollection(features) {
  return {
    type: 'FeatureCollection',
    features: features.filter(Boolean),
  }
}

function severityWeight(severity) {
  return {
    critical: 1,
    high: 0.75,
    medium: 0.45,
    low: 0.25,
  }[String(severity || '').toLowerCase()] || 0.35
}

function coordinatesOf(item, latKey, lngKey) {
  const lat = Number(item?.[latKey])
  const lng = Number(item?.[lngKey])
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return [lng, lat]
}

function validLngLat(coordinate) {
  if (!Array.isArray(coordinate) || coordinate.length < 2) return false
  const lng = Number(coordinate[0])
  const lat = Number(coordinate[1])
  return Number.isFinite(lng) && Number.isFinite(lat)
}

function distanceMeters(start, end) {
  const startLng = Number(start[0])
  const startLat = Number(start[1])
  const endLng = Number(end[0])
  const endLat = Number(end[1])
  const toRadians = Math.PI / 180
  const earthRadiusMeters = 6371000
  const deltaLat = (endLat - startLat) * toRadians
  const deltaLng = (endLng - startLng) * toRadians
  const a = Math.sin(deltaLat / 2) ** 2
    + Math.cos(startLat * toRadians) * Math.cos(endLat * toRadians)
    * Math.sin(deltaLng / 2) ** 2
  return 2 * earthRadiusMeters * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function bearingDegrees(start, end) {
  const startLng = Number(start[0]) * Math.PI / 180
  const startLat = Number(start[1]) * Math.PI / 180
  const endLng = Number(end[0]) * Math.PI / 180
  const endLat = Number(end[1]) * Math.PI / 180
  const deltaLng = endLng - startLng
  const y = Math.sin(deltaLng) * Math.cos(endLat)
  const x = Math.cos(startLat) * Math.sin(endLat)
    - Math.sin(startLat) * Math.cos(endLat) * Math.cos(deltaLng)
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360
}

function interpolateRoutePosition(coordinates, progress) {
  const safeCoordinates = (coordinates || []).filter(validLngLat)
  if (safeCoordinates.length < 2) return null

  const segments = []
  let totalDistance = 0
  for (let index = 1; index < safeCoordinates.length; index += 1) {
    const start = safeCoordinates[index - 1]
    const end = safeCoordinates[index]
    const length = distanceMeters(start, end)
    if (length <= 0) continue
    segments.push({ start, end, length })
    totalDistance += length
  }
  if (!segments.length || totalDistance <= 0) {
    return { coordinate: safeCoordinates[0], bearing: 0 }
  }

  const targetDistance = Math.max(0, Math.min(1, progress)) * totalDistance
  let traversed = 0
  for (const segment of segments) {
    if (traversed + segment.length >= targetDistance) {
      const segmentProgress = (targetDistance - traversed) / segment.length
      return {
        coordinate: [
          segment.start[0] + ((segment.end[0] - segment.start[0]) * segmentProgress),
          segment.start[1] + ((segment.end[1] - segment.start[1]) * segmentProgress),
        ],
        bearing: bearingDegrees(segment.start, segment.end),
      }
    }
    traversed += segment.length
  }

  const finalSegment = segments[segments.length - 1]
  return {
    coordinate: finalSegment.end,
    bearing: bearingDegrees(finalSegment.start, finalSegment.end),
  }
}

function makeRouteAmbulanceElement(route) {
  const element = makeMarkerElement('ambulance', { id: route?.ambulance_id }, true)
  element.classList.add('is-route-runner')
  const icon = element.querySelector('.raid-map-marker-icon')
  if (icon) icon.textContent = '>'
  return element
}

function pointFeature(coordinates, properties) {
  if (!coordinates) return null
  return {
    type: 'Feature',
    properties,
    geometry: {
      type: 'Point',
      coordinates,
    },
  }
}

function boundsForCoordinates(coordinates) {
  if (!coordinates?.length) return null
  const bounds = new maplibregl.LngLatBounds(coordinates[0], coordinates[0])
  coordinates.forEach((coordinate) => bounds.extend(coordinate))
  return bounds
}

function fitMapToRoute(map, route, extraCoordinates = []) {
  const coordinates = [
    ...(route?.coordinates || []),
    ...extraCoordinates.filter(Boolean),
  ]
  const bounds = boundsForCoordinates(coordinates)
  if (!bounds) return
  map.fitBounds(bounds, {
    padding: { top: 96, right: 72, bottom: 120, left: 72 },
    maxZoom: 14,
    duration: 900,
  })
}

function formatEta(value) {
  const numberValue = Number(value || 0)
  if (numberValue <= 0) return '--'
  return `${numberValue.toFixed(numberValue >= 10 ? 0 : 1)} min`
}

function formatStatus(value) {
  return String(value || 'unknown')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function makeMarkerElement(kind, item, selected = false) {
  const button = document.createElement('button')
  button.type = 'button'
  button.className = clsx('raid-map-marker', `raid-map-marker-${kind}`, selected && 'is-selected')
  button.setAttribute('aria-label', `${kind} ${item?.id || item?.name || ''}`)

  const icon = document.createElement('span')
  icon.className = 'raid-map-marker-icon'
  if (kind === 'ambulance') icon.textContent = 'A'
  if (kind === 'incident') icon.textContent = '!'
  if (kind === 'hospital') icon.textContent = 'H'
  if (kind === 'user') icon.textContent = ''

  const label = document.createElement('span')
  label.className = 'raid-map-marker-label'
  label.textContent = kind === 'user' ? 'You' : String(item?.id || item?.name || '').slice(0, 10)

  button.appendChild(icon)
  button.appendChild(label)
  return button
}

function updateGeoJsonSource(map, id, data) {
  const source = map.getSource(id)
  if (source?.setData) {
    source.setData(data || EMPTY_COLLECTION)
  }
}

function addMapSourcesAndLayers(map, mode) {
  if (map.getSource('main-route')) return

  map.addSource('main-route', { type: 'geojson', data: EMPTY_COLLECTION })
  map.addSource('alternate-routes', { type: 'geojson', data: EMPTY_COLLECTION })
  map.addSource('old-route', { type: 'geojson', data: EMPTY_COLLECTION })
  map.addSource('new-route', { type: 'geojson', data: EMPTY_COLLECTION })
  map.addSource('incident-heatmap', { type: 'geojson', data: EMPTY_COLLECTION })
  map.addSource('demand-hotspots', { type: 'geojson', data: EMPTY_COLLECTION })

  if (mode === 'admin') {
    map.addLayer({
      id: 'incident-heat',
      type: 'heatmap',
      source: 'incident-heatmap',
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'weight'], 0, 0, 1, 1],
        'heatmap-intensity': 0.9,
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 18, 13, 34],
        'heatmap-opacity': 0.5,
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0,
          'rgba(15,23,42,0)',
          0.25,
          'rgba(59,130,246,0.35)',
          0.55,
          'rgba(245,158,11,0.55)',
          0.85,
          'rgba(239,68,68,0.8)',
        ],
      },
    })

    map.addLayer({
      id: 'demand-hotspot-circles',
      type: 'circle',
      source: 'demand-hotspots',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'demand'], 0, 8, 1, 24],
        'circle-color': '#38bdf8',
        'circle-opacity': 0.16,
        'circle-stroke-color': '#38bdf8',
        'circle-stroke-width': 1,
        'circle-stroke-opacity': 0.45,
      },
    })
  }

  map.addLayer({
    id: 'alternate-route-lines',
    type: 'line',
    source: 'alternate-routes',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#94a3b8',
      'line-width': 3,
      'line-opacity': 0.35,
      'line-dasharray': [1.5, 2],
    },
  })

  map.addLayer({
    id: 'old-route-line',
    type: 'line',
    source: 'old-route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#ef4444',
      'line-width': 4,
      'line-opacity': 0.7,
      'line-dasharray': [2, 2],
      'line-offset': -4,
    },
  })

  map.addLayer({
    id: 'main-route-casing',
    type: 'line',
    source: 'main-route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#020617',
      'line-width': 9,
      'line-opacity': 0.92,
    },
  })

  map.addLayer({
    id: 'main-route-line',
    type: 'line',
    source: 'main-route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#3b82f6',
      'line-width': 6,
      'line-opacity': 0.96,
    },
  })

  map.addLayer({
    id: 'new-route-line',
    type: 'line',
    source: 'new-route',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#22c55e',
      'line-width': 6,
      'line-opacity': 0.95,
      'line-dasharray': [0.2, 2],
    },
  })
}

function useMarkerSync(mapRef, markersRef, animationsRef, collectionKey, items, getCoordinates, options = {}) {
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    const existing = markersRef.current[collectionKey] || new Map()
    const nextIds = new Set()

    items.forEach((item) => {
      const coordinate = getCoordinates(item)
      if (!coordinate || !item.id) return
      nextIds.add(item.id)

      const selected = options.selectedId === item.id
      let entry = existing.get(item.id)
      if (!entry) {
        const element = makeMarkerElement(options.kind || collectionKey, item, selected)
        element.addEventListener('click', (event) => {
          event.stopPropagation()
          options.onClick?.(item)
        })
        const marker = new maplibregl.Marker({ element, anchor: 'center' })
          .setLngLat(coordinate)
          .addTo(map)
        entry = { marker, element }
        existing.set(item.id, entry)
      }

      entry.element.classList.toggle('is-selected', selected)
      entry.element.classList.toggle('is-muted', Boolean(options.muted?.(item)))
      if (options.kind === 'ambulance') {
        entry.element.classList.toggle('is-en-route', ['en_route', 'dispatched', 'transporting'].includes(item.status))
        entry.element.classList.toggle('is-at-scene', ['at_scene', 'at_hospital'].includes(item.status))
      }
      if (options.kind === 'incident') {
        entry.element.classList.toggle('is-priority-critical', ['critical', 'P1'].includes(item.severity || item.priority))
        entry.element.classList.toggle('is-priority-urgent', ['high', 'P2'].includes(item.severity || item.priority))
        entry.element.classList.toggle('is-resolved', item.status === 'resolved')
      }
      if (options.kind === 'hospital') {
        const load = Number(item.occupancy_pct ?? item.loadPercent ?? 0)
        entry.element.classList.toggle('is-load-amber', load >= 70 && load < 90)
        entry.element.classList.toggle('is-load-red', load >= 90 || Boolean(item.diversion_status))
        entry.element.classList.toggle('is-load-green', load < 70 && !item.diversion_status)
      }

      if (options.animate) {
        const current = entry.marker.getLngLat()
        const from = [current.lng, current.lat]
        const to = coordinate
        const animationKey = `${collectionKey}-${item.id}`
        cancelAnimationFrame(animationsRef.current.get(animationKey))
        const startedAt = performance.now()
        const duration = 1200

        const frame = (now) => {
          const progress = Math.min(1, (now - startedAt) / duration)
          const eased = 1 - ((1 - progress) ** 3)
          entry.marker.setLngLat([
            from[0] + ((to[0] - from[0]) * eased),
            from[1] + ((to[1] - from[1]) * eased),
          ])
          if (progress < 1) {
            animationsRef.current.set(animationKey, requestAnimationFrame(frame))
          }
        }
        animationsRef.current.set(animationKey, requestAnimationFrame(frame))
      } else {
        entry.marker.setLngLat(coordinate)
      }
    })

    existing.forEach((entry, id) => {
      if (!nextIds.has(id)) {
        entry.marker.remove()
        existing.delete(id)
      }
    })

    markersRef.current[collectionKey] = existing
  }, [animationsRef, collectionKey, getCoordinates, items, mapRef, markersRef, options])
}

function useRouteRunner(mapRef, runnerRef, route, mapLoaded) {
  const routeKey = [
    route?.dispatch_id || '',
    route?.ambulance_id || '',
    route?.coordinates?.length || 0,
    route?.coordinates?.[0]?.join(',') || '',
    route?.coordinates?.[route?.coordinates?.length - 1]?.join(',') || '',
  ].join('|')

  useEffect(() => {
    const cleanup = () => {
      if (runnerRef.current?.frameId) {
        cancelAnimationFrame(runnerRef.current.frameId)
      }
      runnerRef.current?.marker?.remove()
      runnerRef.current = null
    }

    const map = mapRef.current
    const coordinates = (route?.coordinates || []).filter(validLngLat)
    if (!map || !mapLoaded || !route?.ambulance_id || coordinates.length < 2) {
      cleanup()
      return cleanup
    }

    cleanup()
    const element = makeRouteAmbulanceElement(route)
    const initialPosition = interpolateRoutePosition(coordinates, 0)
    if (!initialPosition) return cleanup

    const marker = new maplibregl.Marker({ element, anchor: 'center' })
      .setLngLat(initialPosition.coordinate)
      .addTo(map)
    element.style.setProperty('--route-bearing', `${initialPosition.bearing - 90}deg`)

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reducedMotion) {
      runnerRef.current = { marker, frameId: null }
      return cleanup
    }

    const etaMinutes = Number(route.eta_minutes || 0)
    const duration = Math.max(12000, Math.min(36000, etaMinutes > 0 ? etaMinutes * 700 : 18000))
    const startedAt = performance.now()

    const frame = (now) => {
      const progress = ((now - startedAt) % duration) / duration
      const position = interpolateRoutePosition(coordinates, progress)
      if (position) {
        marker.setLngLat(position.coordinate)
        element.style.setProperty('--route-bearing', `${position.bearing - 90}deg`)
      }
      runnerRef.current = {
        marker,
        frameId: requestAnimationFrame(frame),
      }
    }

    runnerRef.current = {
      marker,
      frameId: requestAnimationFrame(frame),
    }
    return cleanup
  }, [mapLoaded, mapRef, route, routeKey, runnerRef])
}

function ModeToggle({ simulationMode, setSimulationMode }) {
  return (
    <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-700 bg-slate-950/80 p-1">
      <button
        type="button"
        onClick={() => setSimulationMode(false)}
        className={clsx(
          'inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-2 text-xs font-semibold transition',
          !simulationMode ? 'bg-blue-500 text-white' : 'text-slate-400 hover:text-slate-100'
        )}
      >
        <RadioTower size={14} />
        Real
      </button>
      <button
        type="button"
        onClick={() => setSimulationMode(true)}
        className={clsx(
          'inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-2 text-xs font-semibold transition',
          simulationMode ? 'bg-amber-500 text-slate-950' : 'text-slate-400 hover:text-slate-100'
        )}
      >
        <FlaskConical size={14} />
        Simulation
      </button>
    </div>
  )
}

function ScoreBars({ options, selectedAmbulanceId }) {
  if (!options?.length) return null
  return (
    <div className="space-y-2">
      {options.slice(0, 4).map((option, index) => {
        const selected = option.ambulance_id === selectedAmbulanceId || index === 0
        const width = Math.max(8, Math.min(100, Number(option.score || 0) * 100))
        return (
          <div
            key={option.ambulance_id}
            className={clsx(
              'rounded-lg border px-3 py-2',
              selected ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-slate-700 bg-slate-950/60'
            )}
          >
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="font-semibold text-slate-100">{option.ambulance_id}</span>
              <span className={selected ? 'text-emerald-300' : 'text-slate-400'}>
                {formatEta(option.total_eta_minutes)}
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
              <div
                className={clsx('h-full rounded-full', selected ? 'bg-emerald-400' : 'bg-slate-500')}
                style={{ width: `${width}%` }}
              />
            </div>
            <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-slate-500">
              <span>D {Math.round((option.score_breakdown?.distance || 0) * 100)}%</span>
              <span>T {Math.round((option.score_breakdown?.traffic || 0) * 100)}%</span>
              <span>H {Math.round((option.score_breakdown?.hospital_load || 0) * 100)}%</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function UserStatusRail({ route }) {
  const eta = Number(route?.eta_minutes || 0)
  const steps = [
    { label: 'Dispatched', active: Boolean(route) },
    { label: 'En route', active: Boolean(route) && eta > 2 },
    { label: eta > 0 ? `Arriving in ${Math.max(1, Math.round(eta))} mins` : 'Arriving', active: Boolean(route) && eta <= 8 },
  ]
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {steps.map((step) => (
        <div
          key={step.label}
          className={clsx(
            'rounded-lg border px-3 py-2 text-xs font-semibold',
            step.active ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 bg-slate-950/60 text-slate-500'
          )}
        >
          {step.label}
        </div>
      ))}
    </div>
  )
}

export default function RealtimeDispatchMap({
  mode = 'admin',
  title,
  selectedIncidentId,
  onSelectIncident,
  serviceCity,
  onServiceCityChange,
  onMapClick,
  showScenarioControls = true,
  showStatusPanel = true,
  showRouteSummary = true,
  fillHeight = false,
  className,
}) {
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const markersRef = useRef({})
  const animationsRef = useRef(new Map())
  const routeRunnerRef = useRef(null)
  const routeFitKeyRef = useRef('')

  const incidents = useDispatchStore((state) => state.incidents)
  const ambulances = useDispatchStore((state) => state.ambulances)
  const hospitals = useDispatchStore((state) => state.hospitals)
  const activeRoute = useDispatchStore((state) => state.activeRoute)
  const alternateRoutes = useDispatchStore((state) => state.alternateRoutes)
  const ambulanceOptions = useDispatchStore((state) => state.ambulanceOptions)
  const routeChange = useDispatchStore((state) => state.routeChange)
  const simulationMode = useDispatchStore((state) => state.simulationMode)
  const setSimulationMode = useDispatchStore((state) => state.setSimulationMode)
  const selectedMapAmbulanceId = useDispatchStore((state) => state.selectedMapAmbulanceId)
  const setSelectedMapAmbulanceId = useDispatchStore((state) => state.setSelectedMapAmbulanceId)
  const wsStatus = useDispatchStore((state) => state.wsStatus)
  const trafficMultiplier = useDispatchStore((state) => state.trafficMultiplier)
  const lastDispatch = useDispatchStore((state) => state.lastDispatch)

  const [mapLoaded, setMapLoaded] = useState(false)
  const [mapError, setMapError] = useState('')
  const [scenarioBusy, setScenarioBusy] = useState('')
  const [demandData, setDemandData] = useState(null)
  const [selectedAmbulance, setSelectedAmbulance] = useState(null)
  const [manualCity, setManualCity] = useState('')
  const [isFullscreen, setIsFullscreen] = useState(false)

  const dispatch = lastDispatch?.data ?? lastDispatch
  const routeIncident = incidents.find((item) => item.id === activeRoute?.incident_id)
  const selectedIncidentById = incidents.find((item) => item.id === selectedIncidentId)
  const routeHospital = hospitals.find((item) => item.id === activeRoute?.hospital_id || item.id === dispatch?.hospital_id)
  const assignedAmbulanceId = activeRoute?.ambulance_id || dispatch?.ambulance_id
  const city = serviceCity
    || manualCity
    || activeRoute?.service_city
    || selectedIncidentById?.city
    || routeIncident?.city
    || routeHospital?.city
    || 'Delhi'
  const selectedIncident = (
    selectedIncidentById && inServiceCity(selectedIncidentById, city)
      ? selectedIncidentById
      : routeIncident && inServiceCity(routeIncident, city)
        ? routeIncident
        : incidents.find((item) => inServiceCity(item, city)) || selectedIncidentById || routeIncident || incidents[0]
  )
  const scopedActiveRoute = !activeRoute?.service_city || sameCity(activeRoute.service_city, city) ? activeRoute : null
  const scopedAlternateRoutes = (alternateRoutes || []).filter((route) => !route.service_city || sameCity(route.service_city, city))
  const routeChangeCity = routeChange?.service_city || routeChange?.new_route?.service_city || routeChange?.old_route?.service_city || routeChange?.city
  const scopedRouteChange = !routeChangeCity || sameCity(routeChangeCity, city) ? routeChange : null
  const blockedRouteMessage = scopedRouteChange?.manual_escalation || scopedRouteChange?.reroute_blocked_reason || (scopedRouteChange && scopedRouteChange.new_route === null && scopedRouteChange.old_route)
    ? (scopedRouteChange.label || 'Manual escalation required; no same-city unit/hospital available')
    : ''

  const visibleAmbulances = useMemo(() => {
    if (mode === 'user') {
      return ambulances.filter((item) => item.id === assignedAmbulanceId)
    }
    const cityAmbulances = ambulances.filter((item) => inServiceCity(item, city))
    const selectedAmbulance = ambulances.find((item) => item.id === scopedActiveRoute?.ambulance_id)
    return mergeUniqueById(cityAmbulances, selectedAmbulance ? [selectedAmbulance] : [])
  }, [ambulances, assignedAmbulanceId, city, mode, scopedActiveRoute?.ambulance_id])

  const routeRunnerActive = Boolean(scopedActiveRoute?.ambulance_id && scopedActiveRoute?.coordinates?.length > 1)
  const markerAmbulances = useMemo(() => {
    if (!routeRunnerActive) return visibleAmbulances
    return visibleAmbulances.filter((item) => item.id !== scopedActiveRoute.ambulance_id)
  }, [routeRunnerActive, scopedActiveRoute?.ambulance_id, visibleAmbulances])

  const visibleIncidents = useMemo(() => {
    if (mode === 'user') {
      return selectedIncident ? [selectedIncident] : []
    }
    const cityIncidents = incidents.filter((item) => inServiceCity(item, city))
    return mergeUniqueById(cityIncidents, selectedIncident ? [selectedIncident] : [])
  }, [city, incidents, mode, selectedIncident])

  const visibleHospitals = useMemo(() => {
    if (mode === 'user') {
      return routeHospital ? [routeHospital] : []
    }
    const cityHospitals = hospitals.filter((item) => inServiceCity(item, city))
    return mergeUniqueById(cityHospitals, routeHospital && inServiceCity(routeHospital, city) ? [routeHospital] : [])
  }, [city, hospitals, mode, routeHospital])

  const userLocation = mode === 'user' && selectedIncident
    ? {
        id: 'user-location',
        location_lat: selectedIncident.location_lat,
        location_lng: selectedIncident.location_lng,
      }
    : null

  useEffect(() => {
    if (mode !== 'admin') return undefined
    let cancelled = false
    fetchDemandHeatmap(city, 30)
      .then((payload) => {
        if (!cancelled) setDemandData(payload)
      })
      .catch(() => {
        if (!cancelled) setDemandData(null)
      })
    return () => {
      cancelled = true
    }
  }, [city, mode])

  useEffect(() => {
    if (selectedAmbulance && !inServiceCity(selectedAmbulance, city)) {
      setSelectedAmbulance(null)
    }
  }, [city, selectedAmbulance])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !onMapClick) return undefined
    const handleClick = (event) => {
      onMapClick({
        lat: Number(event.lngLat.lat),
        lng: Number(event.lngLat.lng),
        city,
      })
    }
    map.on('click', handleClick)
    return () => {
      map.off('click', handleClick)
    }
  }, [city, onMapClick])

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current || isJsdom()) return undefined
    try {
      const center = CITY_CENTERS[city] || [78.9629, 22.5937]
      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: DARK_RASTER_STYLE,
        center,
        zoom: city ? 11 : 4.2,
        attributionControl: false,
      })
      mapRef.current = map
      map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-right')
      map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left')
      map.on('load', () => {
        addMapSourcesAndLayers(map, mode)
        setMapLoaded(true)
      })
      map.on('error', () => setMapError('Map tiles are temporarily unavailable. Live data is still connected.'))
    } catch (error) {
      setMapError(error.message || 'Map failed to initialize')
    }

    return () => {
      animationsRef.current.forEach((id) => cancelAnimationFrame(id))
      if (routeRunnerRef.current?.frameId) {
        cancelAnimationFrame(routeRunnerRef.current.frameId)
      }
      routeRunnerRef.current?.marker?.remove()
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [city, mode])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return
    const center = CITY_CENTERS[city]
    if (center && !scopedActiveRoute?.coordinates?.length) {
      map.easeTo({ center, zoom: 11, duration: 700 })
    }
  }, [city, mapLoaded, scopedActiveRoute?.coordinates?.length])

  useEffect(() => {
    const timer = window.setTimeout(() => mapRef.current?.resize(), 120)
    return () => window.clearTimeout(timer)
  }, [isFullscreen])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return

    updateGeoJsonSource(map, 'main-route', featureCollection([routeFeature(scopedActiveRoute)]))
    updateGeoJsonSource(
      map,
      'alternate-routes',
      featureCollection(scopedAlternateRoutes.map((route) => routeFeature(route, 'alternate')))
    )
    updateGeoJsonSource(map, 'old-route', featureCollection([routeFeature(scopedRouteChange?.old_route, 'old')]))
    updateGeoJsonSource(map, 'new-route', featureCollection([routeFeature(scopedRouteChange?.new_route, 'new')]))

    const heatmapFeatures = visibleIncidents
      .map((incident) => pointFeature(
        coordinatesOf(incident, 'location_lat', 'location_lng'),
        {
          weight: severityWeight(incident.severity),
          severity: incident.severity,
        }
      ))
      .filter(Boolean)
    updateGeoJsonSource(map, 'incident-heatmap', featureCollection(heatmapFeatures))

    const demandFeatures = (demandData?.hotspots || [])
      .slice(0, 20)
      .map((hotspot) => pointFeature(
        coordinatesOf(hotspot, 'lat', 'lng'),
        {
          demand: Number(hotspot.demand_score || 0),
        }
      ))
      .filter(Boolean)
    updateGeoJsonSource(map, 'demand-hotspots', featureCollection(demandFeatures))
  }, [demandData, mapLoaded, scopedActiveRoute, scopedAlternateRoutes, scopedRouteChange, visibleIncidents])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded || !map.getLayer('main-route-line')) return
    const multiplier = Number(scopedActiveRoute?.traffic_multiplier || trafficMultiplier || 1)
    const routeColor = multiplier >= 2.2 ? '#ff4757' : multiplier >= 1.4 ? '#f6a623' : '#00d4aa'
    map.setPaintProperty('main-route-line', 'line-color', routeColor)
  }, [mapLoaded, scopedActiveRoute?.traffic_multiplier, trafficMultiplier])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return undefined
    let step = 0
    const timer = setInterval(() => {
      step = (step + 0.25) % 4
      if (mapRef.current !== map || !map.style || !map.isStyleLoaded()) {
        return
      }
      try {
        if (map.getLayer('new-route-line')) {
          map.setPaintProperty('new-route-line', 'line-dasharray', [0.2 + step, 2, 1.2, 2])
        }
      } catch {
        clearInterval(timer)
      }
    }, 180)
    return () => clearInterval(timer)
  }, [mapLoaded, routeChange?.timestamp])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapLoaded) return
    const fitKey = `${scopedActiveRoute?.dispatch_id || ''}-${scopedActiveRoute?.coordinates?.length || 0}-${city}`
    if (!scopedActiveRoute?.coordinates?.length || fitKey === routeFitKeyRef.current) return
    routeFitKeyRef.current = fitKey
    const extras = [
      coordinatesOf(selectedIncident, 'location_lat', 'location_lng'),
      coordinatesOf(routeHospital, 'lat', 'lng'),
    ]
    fitMapToRoute(map, scopedActiveRoute, extras)
  }, [city, mapLoaded, routeHospital, scopedActiveRoute, selectedIncident])

  useMarkerSync(
    mapRef,
    markersRef,
    animationsRef,
    'ambulances',
    markerAmbulances,
    (item) => coordinatesOf(item, 'current_lat', 'current_lng'),
    {
      kind: 'ambulance',
      animate: true,
      selectedId: selectedMapAmbulanceId || scopedActiveRoute?.ambulance_id || assignedAmbulanceId,
      onClick: (item) => {
        setSelectedMapAmbulanceId(item.id)
        setSelectedAmbulance(item)
      },
      muted: (item) => item.status === 'unavailable',
    }
  )

  useMarkerSync(
    mapRef,
    markersRef,
    animationsRef,
    'incidents',
    visibleIncidents,
    (item) => coordinatesOf(item, 'location_lat', 'location_lng'),
    {
      kind: 'incident',
      selectedId: selectedIncident?.id,
      onClick: (item) => {
        setManualCity(item.city || '')
        onSelectIncident?.(item.id)
      },
      muted: (item) => item.status === 'resolved',
    }
  )

  useRouteRunner(mapRef, routeRunnerRef, scopedActiveRoute, mapLoaded)

  useMarkerSync(
    mapRef,
    markersRef,
    animationsRef,
    'hospitals',
    visibleHospitals,
    (item) => coordinatesOf(item, 'lat', 'lng'),
    {
      kind: 'hospital',
      selectedId: routeHospital?.id,
      muted: (item) => item.diversion_status,
      onClick: () => {},
    }
  )

  useMarkerSync(
    mapRef,
    markersRef,
    animationsRef,
    'user',
    userLocation ? [userLocation] : [],
    (item) => coordinatesOf(item, 'location_lat', 'location_lng'),
    {
      kind: 'user',
      selectedId: userLocation?.id,
      onClick: () => {},
    }
  )

  async function runScenario(type) {
    setScenarioBusy(type)
    try {
      await triggerScenario(type)
    } finally {
      setScenarioBusy('')
    }
  }

  function recenter() {
    const map = mapRef.current
    if (!map) return
    if (scopedActiveRoute?.coordinates?.length) {
      fitMapToRoute(map, scopedActiveRoute)
      return
    }
    map.easeTo({ center: CITY_CENTERS[city] || [78.9629, 22.5937], zoom: 11, duration: 700 })
  }

  if (isJsdom()) {
    return (
      <div className={clsx('rounded-xl border border-border bg-slate-950 p-4', className)} data-testid="realtime-map-fallback">
        <p className="text-sm text-slate-300">Realtime map preview</p>
      </div>
    )
  }

  return (
    <section
      className={clsx(
        'relative overflow-hidden border border-slate-700 bg-slate-950 shadow-2xl shadow-black/30',
        isFullscreen
          ? 'fixed inset-0 z-[80] rounded-none border-0'
          : 'rounded-xl',
        className
      )}
    >
      <div
        ref={mapContainerRef}
        className={clsx(
          'w-full',
          isFullscreen
            ? 'h-screen min-h-screen'
            : fillHeight
              ? 'h-full min-h-[680px]'
              : 'h-[68vh] min-h-[620px] max-h-[780px]'
        )}
      />

      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(15,23,42,0.34),transparent_22%,transparent_74%,rgba(15,23,42,0.58))]" />

      {mapError ? (
        <div className="absolute left-4 right-4 top-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          {mapError}
        </div>
      ) : null}

      {showStatusPanel ? (
      <div className="absolute left-3 top-3 w-[calc(100%-5.5rem)] max-w-[340px] rounded-xl border border-slate-700 bg-slate-950/88 p-3 shadow-xl shadow-black/30 backdrop-blur sm:left-4 sm:top-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-2 text-blue-300">
                {mode === 'admin' ? <Crosshair size={16} /> : <Navigation size={16} />}
              </span>
              <div>
                <h2 className="text-sm font-semibold text-white">
                  {title || (mode === 'admin' ? 'Simulation Route Map' : 'Ambulance Tracking')}
                </h2>
                <p className="text-xs text-slate-500">{city} service area</p>
              </div>
            </div>
          </div>
          <Badge variant={wsStatus === 'connected' ? 'success' : 'warning'}>
            {wsStatus === 'connected' ? 'Live' : 'Syncing'}
          </Badge>
        </div>

        {mode === 'admin' ? (
          <label className="mt-3 block text-xs text-slate-400">
            Service city
            <select
              value={city}
              onChange={(event) => {
                setManualCity(event.target.value)
                onServiceCityChange?.(event.target.value)
                onSelectIncident?.('')
              }}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-100 outline-none focus:ring-2 focus:ring-blue-500"
            >
              {CITY_NAMES.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-2">
            <p className="text-slate-500">Units</p>
            <p className="mt-0.5 font-semibold text-white">{visibleAmbulances.length}</p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-2">
            <p className="text-slate-500">Incidents</p>
            <p className="mt-0.5 font-semibold text-white">{visibleIncidents.length}</p>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900/80 px-2 py-2">
            <p className="text-slate-500">Traffic</p>
            <p className={clsx('mt-0.5 font-semibold', trafficMultiplier > 1.5 ? 'text-amber-300' : 'text-emerald-300')}>
              {Number(trafficMultiplier || 1).toFixed(1)}x
            </p>
          </div>
        </div>

        {mode === 'admin' ? (
          <div className="mt-3">
            <ModeToggle simulationMode={simulationMode} setSimulationMode={setSimulationMode} />
            {simulationMode && showScenarioControls ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                {SIMULATION_SCENARIOS.map(({ type, label, icon: Icon }) => (
                  <Button
                    key={type}
                    size="sm"
                    variant={type === 'cardiac' ? 'danger' : 'secondary'}
                    icon={Icon}
                    loading={scenarioBusy === type}
                    disabled={Boolean(scenarioBusy)}
                    className="min-w-0"
                    onClick={() => runScenario(type)}
                  >
                    <span className="truncate">{label}</span>
                  </Button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <div className="mt-3">
            <UserStatusRail route={scopedActiveRoute} />
          </div>
        )}
      </div>
      ) : null}

      <div className="absolute right-3 top-3 flex gap-2 sm:right-4 sm:top-4">
        <button
          type="button"
          onClick={recenter}
          className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-700 bg-slate-950/90 text-slate-300 shadow-lg shadow-black/25 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label="Recenter map"
          title="Recenter map"
        >
          <LocateFixed size={18} />
        </button>
        <button
          type="button"
          onClick={() => setIsFullscreen((value) => !value)}
          className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-700 bg-slate-950/90 text-slate-300 shadow-lg shadow-black/25 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          aria-label={isFullscreen ? 'Exit fullscreen map' : 'Open fullscreen map'}
          title={isFullscreen ? 'Exit fullscreen map' : 'Fullscreen map'}
        >
          {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
        </button>
      </div>

      {showRouteSummary && scopedActiveRoute ? (
        <div className="absolute bottom-3 left-3 right-3 rounded-xl border border-slate-700 bg-slate-950/90 p-3 shadow-xl shadow-black/35 backdrop-blur sm:bottom-4 sm:left-4 sm:right-auto sm:w-[380px]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success">{scopedActiveRoute.status_label || 'En route'}</Badge>
                <span className="text-xs text-slate-500">
                  {scopedActiveRoute.ambulance_id} to {scopedActiveRoute.hospital_id}
                </span>
              </div>
              <p className="mt-2 text-2xl font-bold text-white">{formatEta(scopedActiveRoute.eta_minutes)}</p>
            </div>
            <span className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2 text-emerald-300">
              <Ambulance size={18} />
            </span>
          </div>
          {blockedRouteMessage ? (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <span>{blockedRouteMessage}</span>
            </div>
          ) : scopedRouteChange?.label ? (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              <AlertTriangle size={14} />
              <span>{scopedRouteChange.label}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {showRouteSummary && !scopedActiveRoute && blockedRouteMessage ? (
        <div className="absolute bottom-3 left-3 right-3 rounded-xl border border-red-500/35 bg-red-950/90 p-3 text-sm text-red-100 shadow-xl shadow-black/35 backdrop-blur sm:bottom-4 sm:left-4 sm:right-auto sm:w-[380px]">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-300" />
            <div>
              <p className="font-semibold text-white">Manual escalation required</p>
              <p className="mt-1 text-xs text-red-200">{blockedRouteMessage}</p>
            </div>
          </div>
        </div>
      ) : null}

      {mode === 'admin' && isFullscreen ? (
        <div className="absolute bottom-4 right-4 hidden w-[330px] rounded-xl border border-slate-700 bg-slate-950/90 p-3 shadow-xl shadow-black/35 backdrop-blur xl:block">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-2 text-blue-300">
                <Activity size={15} />
              </span>
              <div>
                <p className="text-sm font-semibold text-white">AI Options</p>
                <p className="text-xs text-slate-500">Distance, traffic, hospital load</p>
              </div>
            </div>
            <Badge variant={ambulanceOptions.length ? 'info' : 'neutral'}>
              {ambulanceOptions.length || 0}
            </Badge>
          </div>
          <ScoreBars options={ambulanceOptions} selectedAmbulanceId={scopedActiveRoute?.ambulance_id} />
        </div>
      ) : null}

      {selectedAmbulance && mode === 'admin' ? (
        <div className="absolute right-3 top-[76px] w-[280px] rounded-xl border border-slate-700 bg-slate-950/92 p-3 shadow-xl shadow-black/35 backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">{selectedAmbulance.id}</p>
              <p className="text-xs text-slate-500">{selectedAmbulance.city} - {selectedAmbulance.zone}</p>
            </div>
            <button
              type="button"
              className="h-8 w-8 rounded-lg text-slate-500 transition hover:bg-slate-800 hover:text-white"
              onClick={() => setSelectedAmbulance(null)}
              aria-label="Close ambulance details"
            >
              X
            </button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-lg border border-slate-700 bg-slate-900/80 p-2">
              <p className="text-slate-500">Status</p>
              <p className="mt-1 font-semibold text-slate-100">{formatStatus(selectedAmbulance.status)}</p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/80 p-2">
              <p className="text-slate-500">Readiness</p>
              <p className="mt-1 font-semibold text-emerald-300">
                {Math.round(Number(selectedAmbulance.crew_readiness || 0) * 100)}%
              </p>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {(selectedAmbulance.equipment || []).slice(0, 5).map((item) => (
              <span key={item} className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-400">
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {isFullscreen ? (
        <div className="pointer-events-none absolute bottom-4 left-1/2 hidden -translate-x-1/2 items-center gap-3 rounded-full border border-slate-700 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400 backdrop-blur lg:flex">
          <span className="inline-flex items-center gap-1.5"><Ambulance size={13} /> Ambulance</span>
          <span className="inline-flex items-center gap-1.5"><MapPin size={13} /> Incident</span>
          <span className="inline-flex items-center gap-1.5"><Hospital size={13} /> Hospital</span>
          <span className="inline-flex items-center gap-1.5"><Building2 size={13} /> Capacity</span>
          {mode === 'admin' ? <span className="inline-flex items-center gap-1.5"><Zap size={13} /> Demand</span> : null}
        </div>
      ) : null}
    </section>
  )
}
