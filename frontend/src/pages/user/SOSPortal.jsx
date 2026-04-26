import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Mic, MicOff } from 'lucide-react'

import api from '../../services/api'
import useDispatchStore from '../../store/dispatchStore'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Card from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

const CITY_CENTERS = {
  Delhi:     { lat: 28.6139, lng: 77.2090 },
  Mumbai:    { lat: 19.0760, lng: 72.8777 },
  Bengaluru: { lat: 12.9716, lng: 77.5946 },
  Chennai:   { lat: 13.0827, lng: 80.2707 },
  Hyderabad: { lat: 17.3850, lng: 78.4867 },
}

const defaultCity = 'Delhi'
const SPEECH_LANGUAGE_PREFIXES = ['hi', 'bn', 'ta', 'te', 'kn', 'mr', 'gu', 'pa', 'ml', 'ur', 'en']
const SOS_REPORT_RULES = [
  {
    label: 'breathing emergency',
    terms: ['not breathing', 'cannot breathe', "can't breathe", 'difficulty breathing', 'gasping', 'choking', 'sans nahi', 'saans nahi', 'sans lene mein takleef'],
  },
  {
    label: 'loss of consciousness',
    terms: ['unconscious', 'unresponsive', 'fainted and not waking', 'hosh nahi', 'behosh'],
  },
  {
    label: 'major bleeding',
    terms: ['severe bleeding', 'heavy bleeding', 'bleeding badly', 'blood not stopping', 'bahut khoon', 'zyada khoon', 'khoon ruk nahi raha'],
  },
  {
    label: 'stroke symptoms',
    terms: ['stroke', 'face drooping', 'slurred speech', 'one side weakness', 'paralysis', 'lakwa'],
  },
  {
    label: 'cardiac arrest',
    terms: ['cardiac arrest', 'heart attack', 'dil ka dora', 'no pulse', 'nab nahi'],
  },
]
const CHEST_PAIN_TERMS = ['chest pain', 'chest mei pain', 'chest mein pain', 'chest me pain', 'seene mein dard', 'seena dard']
const HIGH_RISK_CONTEXT_TERMS = ['severe', 'bahut', 'very', 'sweating', 'collapse', 'faint', 'breath', 'sans', 'saans', 'left arm', 'jaw pain', 'older', 'elderly']
const LOW_ACUITY_TERMS = ['mild', 'minor', 'small cut', 'not serious', 'stable', 'normal breathing', 'no bleeding', 'thoda', 'halka']

function getPreferredSpeechLanguage() {
  const languages = navigator.languages?.length
    ? navigator.languages
    : [navigator.language].filter(Boolean)
  const preferred = languages.find((language) => {
    const prefix = language.toLowerCase().split('-')[0]
    return SPEECH_LANGUAGE_PREFIXES.includes(prefix)
  })
  return preferred || 'en-IN'
}

function includesAny(normalized, terms) {
  return terms.some((term) => normalized.includes(term))
}

function isNegated(normalized, term) {
  return [
    `no ${term}`,
    `not ${term}`,
    `without ${term}`,
    `${term} nahi`,
    `${term} nahi hai`,
    `${term} nahin`,
    `${term} nahin hai`,
  ].some((phrase) => normalized.includes(phrase))
}

function hasAffirmedTerm(normalized, terms) {
  return terms.some((term) => normalized.includes(term) && !isNegated(normalized, term))
}

function classifyReportPriority(report) {
  const normalized = report.toLowerCase().replace(/\s+/g, ' ').trim()
  if (normalized.length < 8) return null

  const immediateRule = SOS_REPORT_RULES.find((rule) => hasAffirmedTerm(normalized, rule.terms))
  if (immediateRule) {
    return immediateRule.label
  }

  const hasChestPain = hasAffirmedTerm(normalized, CHEST_PAIN_TERMS)
  if (!hasChestPain) {
    return null
  }

  const hasLowAcuityContext = includesAny(normalized, LOW_ACUITY_TERMS)
  const hasHighRiskContext = includesAny(normalized, HIGH_RISK_CONTEXT_TERMS)
  if (!hasLowAcuityContext || hasHighRiskContext) {
    return 'cardiac-risk report'
  }

  return null
}

function SelectField({ label, value, onChange, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-slate-300">{label}</label>
      <select
        value={value}
        onChange={onChange}
        className="w-full rounded-xl border border-border bg-slate-800 px-4 py-2.5 text-sm text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      >
        {children}
      </select>
    </div>
  )
}

export default function SOSPortal() {
  const navigate = useNavigate()
  const hospitals = useDispatchStore((state) => state.hospitals)
  const ambulances = useDispatchStore((state) => state.ambulances)
  const setLastDispatch = useDispatchStore((state) => state.setLastDispatch)

  const [name, setName] = useState('')
  const [age, setAge] = useState('')
  const [gender, setGender] = useState('male')
  const [mobile, setMobile] = useState('')
  const [complaint, setComplaint] = useState('')
  const [city, setCity] = useState('Delhi')
  const [lat, setLat] = useState(28.6139)
  const [lng, setLng] = useState(77.2090)
  const [sosMode, setSosMode] = useState(true)
  const [autoPrioritySignal, setAutoPrioritySignal] = useState(null)
  const [voiceSupported, setVoiceSupported] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceMessage, setVoiceMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [formError, setFormError] = useState(null)
  const [patientId, setPatientId] = useState(null)
  const [status, setStatus] = useState('success')
  const [message, setMessage] = useState('')
  const [plan, setPlan] = useState(null)
  const recognitionRef = useRef(null)
  const voiceBaseComplaintRef = useRef('')

  useEffect(() => {
    if (!formError) return undefined
    const t = setTimeout(() => setFormError(null), 6000)
    return () => clearTimeout(t)
  }, [formError])

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition
    setVoiceSupported(Boolean(SpeechRecognition))

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onend = null
        recognitionRef.current.onerror = null
        recognitionRef.current.onresult = null
        try {
          recognitionRef.current.stop()
        } catch {
          // SpeechRecognition can throw if it has already stopped.
        }
      }
    }
  }, [])

  useEffect(() => {
    const signal = classifyReportPriority(complaint)
    setAutoPrioritySignal(signal)
    if (signal) {
      setSosMode(true)
    }
  }, [complaint])

  function resetForm() {
    stopVoiceReport({ showMessage: false })
    setName('')
    setAge('')
    setGender('male')
    setMobile('')
    setComplaint('')
    setCity(defaultCity)
    setLat(CITY_CENTERS[defaultCity].lat)
    setLng(CITY_CENTERS[defaultCity].lng)
    setSosMode(true)
    setAutoPrioritySignal(null)
    setIsListening(false)
    setVoiceMessage('')
    setLoading(false)
    setFormError(null)
    setPatientId(null)
    setStatus('success')
    setMessage('')
    setPlan(null)
  }

  function handleCityChange(event) {
    const c = event.target.value
    setCity(c)
    const center = CITY_CENTERS[c]
    if (center) {
      setLat(center.lat)
      setLng(center.lng)
    }
  }

  function validate() {
    if (!name.trim()) {
      setFormError('Name is required')
      return false
    }
    if (!age || Number(age) < 1) {
      setFormError('Valid age is required')
      return false
    }
    if (!mobile.trim()) {
      setFormError('Mobile number is required')
      return false
    }
    if (!complaint.trim()) {
      setFormError('Emergency report is required')
      return false
    }
    return true
  }

  function stopVoiceReport({ showMessage = true } = {}) {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // SpeechRecognition can throw if it has already stopped.
      }
    }
    setIsListening(false)
    if (showMessage) {
      setVoiceMessage('Voice report stopped. You can edit the text before submitting.')
    }
  }

  function toggleVoiceReport() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      setVoiceSupported(false)
      setVoiceMessage('Voice report is not supported in this browser. Please type the emergency details.')
      return
    }

    if (isListening) {
      stopVoiceReport()
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = getPreferredSpeechLanguage()
    recognition.continuous = true
    recognition.interimResults = true
    voiceBaseComplaintRef.current = complaint.trim()
    recognitionRef.current = recognition

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim()
      const base = voiceBaseComplaintRef.current
      setComplaint([base, transcript].filter(Boolean).join(' ').trim())
    }

    recognition.onerror = (event) => {
      setIsListening(false)
      setVoiceMessage(
        event.error === 'not-allowed'
          ? 'Microphone permission was blocked. Please allow microphone access or type the report.'
          : 'Voice report stopped. You can try again or type the details.'
      )
    }

    recognition.onend = () => {
      if (recognitionRef.current === recognition) {
        recognitionRef.current = null
      }
      setIsListening(false)
      setVoiceMessage((current) => (
        current === 'Listening. Speak naturally. The report will be checked for language and triage signals.'
          ? 'Voice report stopped. You can edit the text before submitting.'
          : current
      ))
    }

    try {
      recognition.start()
      setVoiceSupported(true)
      setIsListening(true)
      setVoiceMessage('Listening. Speak naturally. The report will be checked for language and triage signals.')
    } catch {
      setIsListening(false)
      setVoiceMessage('Voice report could not start. Please try again or type the details.')
    }
  }

  async function handleSubmit() {
    if (!validate()) return

    setLoading(true)
    setFormError(null)
    setPatientId(null)
    setStatus('success')
    setMessage('')
    setPlan(null)

    try {
      const result = await api.post('/patients', {
        name: name.trim(),
        age: Number(age),
        gender,
        mobile: mobile.trim(),
        location_lat: lat,
        location_lng: lng,
        chief_complaint: complaint.trim(),
        sos_mode: sosMode,
      })

      const raw = result.data
      const status = raw?.status || 'success'
      const message = raw?.message || ''
      const plan = raw?.data?.dispatch_plan
                 || raw?.dispatch_plan
                 || raw?.data
                 || null
      setStatus(status)
      setMessage(message)
      setPlan(plan)
      if (plan) setLastDispatch(plan)
      setPatientId(raw?.data?.patient?.id || raw?.patient?.id || null)
    } catch (err) {
      setFormError(err.response?.data?.message || err.message || 'Unable to request emergency dispatch.')
    } finally {
      setLoading(false)
    }
  }

  const hasResult = Boolean(patientId || plan || message)
  const dispatchPlan = plan?.data ?? plan
  const eta = plan?.eta_minutes ?? plan?.data?.eta_minutes ?? null
  const assignedAmbulance = ambulances.find((ambulance) => ambulance.id === dispatchPlan?.ambulance_id)
  const assignedHospital = hospitals.find((hospital) => hospital.id === dispatchPlan?.hospital_id)

  return (
    <div className="mx-auto max-w-2xl">
      <div
        className="mb-6 rounded-2xl p-6"
        style={{ background: 'linear-gradient(135deg, #7f1d1d, #991b1b)' }}
      >
        <div className="mb-2 flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"/>
            <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500"/>
          </span>
          <h1 className="text-2xl font-bold text-white">
            Emergency SOS
          </h1>
        </div>
        <p className="mt-1 text-sm text-red-200">
          Help is on the way. Fill in details for fastest dispatch.
        </p>
      </div>

      {hasResult ? (
        <Card className="border-l-4 border-l-emerald-500">
          <div className="flex items-start gap-4">
            <CheckCircle2 size={30} className="mt-0.5 text-emerald-400"/>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-white">SOS Received</h2>
              <p className="mt-1 font-mono text-sm text-slate-400">
                Case ID: {patientId || 'Pending'}
              </p>
            </div>
          </div>

          {status === 'fallback' && (
            <div className="mb-4 mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-400">
              Fallback dispatch active {'\u2014'} {message || 'nearest available unit'}
            </div>
          )}

          <div className="mt-6 rounded-2xl border border-border bg-slate-800/50 p-4">
            <p className="text-sm font-semibold text-slate-200">Ambulance Assigned</p>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <span className="text-2xl font-bold text-white">
                {dispatchPlan?.ambulance_id || 'Pending allocation'}
              </span>
              {assignedAmbulance?.type ? (
                <Badge variant="info">{assignedAmbulance.type}</Badge>
              ) : null}
            </div>
            <div className="mt-4 flex items-end">
              <span className="text-2xl font-bold text-emerald-400">
                {eta ? `${Number(eta).toFixed(1)} min` : 'Calculating...'}
              </span>
              <span className="ml-2 text-sm text-slate-400">ETA</span>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-border bg-slate-800/50 p-4">
            <p className="text-sm font-semibold text-slate-200">Destination Hospital</p>
            <p className="mt-3 text-lg font-semibold text-white">
              {assignedHospital?.name || dispatchPlan?.hospital_id || 'Awaiting assignment'}
            </p>
            {assignedHospital?.city ? (
              <p className="mt-1 text-sm text-slate-400">{assignedHospital.city}</p>
            ) : null}
          </div>

          <div className="mt-4 rounded-2xl border border-border bg-slate-800/50 p-4">
            <p className="text-sm font-semibold text-slate-200">AI Decision</p>
            <p className="mt-3 text-sm italic text-slate-300">
              {dispatchPlan?.explanation_text || message || 'Dispatch engine is evaluating the best route.'}
            </p>
          </div>

          <Button
            variant="primary"
            className="mt-4 w-full"
            onClick={() => navigate('/user/status')}
          >
            Track My Ambulance
          </Button>
          <Button
            variant="ghost"
            className="mt-2 w-full"
            onClick={resetForm}
          >
            Submit Another Request
          </Button>
        </Card>
      ) : (
        <Card>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Full Name"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Input
              label="Age"
              type="number"
              value={age}
              onChange={(event) => setAge(event.target.value)}
            />
            <SelectField
              label="Gender"
              value={gender}
              onChange={(event) => setGender(event.target.value)}
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </SelectField>
            <Input
              label="Mobile"
              type="tel"
              value={mobile}
              onChange={(event) => setMobile(event.target.value)}
            />
            <SelectField
              label="City"
              value={city}
              onChange={handleCityChange}
            >
              {Object.keys(CITY_CENTERS).map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </SelectField>
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-slate-300">Priority SOS</label>
              <div className="flex min-h-16 items-center justify-between gap-3 rounded-xl border border-border bg-slate-800 px-4 py-3">
                <div className="min-w-0">
                  <span className="block text-sm text-slate-200">Priority SOS</span>
                  <span className="block text-xs text-slate-500">
                    {autoPrioritySignal
                      ? `Priority enabled from report: ${autoPrioritySignal}`
                      : sosMode ? 'Critical priority enabled' : 'Standard priority'}
                  </span>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={sosMode}
                  aria-label="Priority SOS mode"
                  title={autoPrioritySignal ? 'Priority is locked on because the report contains a critical signal.' : 'Toggle Priority SOS mode'}
                  disabled={Boolean(autoPrioritySignal)}
                  onClick={() => setSosMode((current) => !current)}
                  className={`relative inline-flex h-6 w-11 shrink-0 rounded-full ring-1 ring-inset transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300/70 disabled:cursor-not-allowed ${
                    sosMode ? 'bg-red-500 ring-red-400/40' : 'bg-slate-700 ring-slate-500/50'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      sosMode ? 'translate-x-5' : 'translate-x-0.5'
                    }`}
                  />
                  <span className="sr-only">{sosMode ? 'On' : 'Off'}</span>
                </button>
              </div>
            </div>
          </div>

          <div className="mt-4">
            <div className="mb-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <label className="block text-sm font-medium text-slate-300">
                  Emergency Report
                </label>
                <p className="mt-1 text-xs text-slate-500">
                  Type or speak the complaint. Triage runs from this report.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant={isListening ? 'danger' : 'secondary'}
                  size="sm"
                  icon={isListening ? MicOff : Mic}
                  onClick={toggleVoiceReport}
                >
                  {isListening ? 'Stop voice' : 'Voice report'}
                </Button>
              </div>
            </div>
            <textarea
              rows={4}
              value={complaint}
              onChange={(event) => setComplaint(event.target.value)}
              placeholder={`Describe the emergency in any language.\nExample: mujhe chest mei pain hai.`}
              className="w-full rounded-xl border border-border bg-slate-800 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            />
            {voiceMessage ? (
              <p className={`mt-2 text-xs ${isListening ? 'text-red-300' : 'text-slate-500'}`}>
                {voiceMessage}
              </p>
            ) : null}
            {!voiceSupported ? (
              <p className="mt-2 text-xs text-slate-500">
                Voice report works in browsers with Web Speech recognition support.
              </p>
            ) : null}
            <p
              className="mt-1 text-xs text-slate-500"
              title="You can write or speak in any supported language"
            >
              Speak naturally. The system detects language and translates supported Indian-language reports before triage.
            </p>
          </div>

          {formError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-red-400 text-sm flex items-start gap-2">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0"/>
              <span>{formError}</span>
            </div>
          )}

          <Button
            variant="danger"
            size="lg"
            className="mt-4 w-full"
            loading={loading}
            onClick={handleSubmit}
          >
            {loading ? 'Dispatching...' : 'Request Emergency Dispatch'}
          </Button>
        </Card>
      )}
    </div>
  )
}
