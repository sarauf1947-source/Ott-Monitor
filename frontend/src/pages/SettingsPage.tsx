// frontend/src/pages/SettingsPage.tsx  (v2.3 - Notifications tab updated)
// Change: NotificationsTab now has a "Toast duration" slider (1-10 seconds)
// that saves to localStorage key 'toast_duration' read by Layout.tsx.
// All other tabs (SMTP, Webhooks, Alerts) are unchanged from v2.2.
import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  getSmtp, saveSmtp, testSmtp,
  getWebhooks, addWebhook, removeWebhook, testWebhook,
  getAlertConfig, saveAlertConfig,
  getNotifications, saveNotifications,
} from '@/services/apiV2'
import { PageHeader } from '@/components/common'
import { useAuth } from '@/context/AuthContext'

type Tab = 'smtp' | 'webhooks' | 'alerts' | 'notifications'

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>('smtp')
  const { isAdmin }   = useAuth()
  const tabs: { key: Tab; label: string }[] = [
    { key: 'smtp',          label: 'SMTP'          },
    { key: 'webhooks',      label: 'Webhooks'      },
    { key: 'alerts',        label: 'Alerts'        },
    { key: 'notifications', label: 'Notifications' },
  ]
  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Settings" subtitle="Runtime configuration" />
      <div className="flex-1 overflow-auto p-6">
        {!isAdmin && (
          <div className="mb-4 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg px-4 py-3 text-sm">
            You have read-only access. Contact an admin to make changes.
          </div>
        )}
        <div className="flex border-b border-gray-200 mb-6 gap-1">
          {tabs.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
                tab === t.key
                  ? 'bg-white border border-b-white border-gray-200 -mb-px text-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}>
              {t.label}
            </button>
          ))}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          {tab === 'smtp'          && <SmtpTab />}
          {tab === 'webhooks'      && <WebhooksTab />}
          {tab === 'alerts'        && <AlertsTab />}
          {tab === 'notifications' && <NotificationsTab />}
        </div>
      </div>
    </div>
  )
}

// ---- SMTP -------------------------------------------------------------------
function SmtpTab() {
  const { isAdmin } = useAuth()
  const { data }    = useQuery({ queryKey: ['settings','smtp'], queryFn: getSmtp })
  const [form, setForm] = useState({ host:'', port:587, username:'', password:'', use_tls:true, from_email:'', from_name:'OTT Monitor' })
  const [testEmail, setTestEmail] = useState('')
  const [msg,       setMsg]       = useState('')
  useEffect(() => { if (data) setForm(data) }, [data])
  const saveMut = useMutation({ mutationFn: () => saveSmtp(form),
    onSuccess: () => flash(setMsg, 'SMTP settings saved', true),
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })
  const testMut = useMutation({ mutationFn: () => testSmtp(testEmail),
    onSuccess: () => flash(setMsg, 'Test email sent', true),
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })
  return (
    <div className="space-y-5 max-w-2xl">
      <h2 className="text-base font-semibold text-gray-900">SMTP Configuration</h2>
      <Msg msg={msg} />
      <div className="grid grid-cols-2 gap-4">
        <F label="Host"       value={form.host}       onChange={v=>setForm(f=>({...f,host:v}))}       disabled={!isAdmin} />
        <F label="Port" type="number" value={String(form.port)} onChange={v=>setForm(f=>({...f,port:+v}))} disabled={!isAdmin} />
        <F label="Username"   value={form.username}   onChange={v=>setForm(f=>({...f,username:v}))}   disabled={!isAdmin} />
        <F label="Password" type="password" value={form.password} onChange={v=>setForm(f=>({...f,password:v}))} disabled={!isAdmin} placeholder="Leave blank to keep" />
        <F label="From Email" value={form.from_email} onChange={v=>setForm(f=>({...f,from_email:v}))} disabled={!isAdmin} />
        <F label="From Name"  value={form.from_name}  onChange={v=>setForm(f=>({...f,from_name:v}))}  disabled={!isAdmin} />
      </div>
      <Chk label="Enable TLS / STARTTLS" checked={form.use_tls} disabled={!isAdmin} onChange={v=>setForm(f=>({...f,use_tls:v}))} />
      {isAdmin && (
        <div className="flex items-center gap-3 flex-wrap pt-2">
          <button className="btn-primary" onClick={()=>saveMut.mutate()} disabled={saveMut.isPending}>Save SMTP</button>
          <input className="input w-52" placeholder="Test recipient email" value={testEmail} onChange={e=>setTestEmail(e.target.value)} />
          <button className="btn-secondary" onClick={()=>testMut.mutate()} disabled={testMut.isPending||!testEmail}>Send Test</button>
        </div>
      )}
    </div>
  )
}

// ---- Webhooks ---------------------------------------------------------------
function WebhooksTab() {
  const { isAdmin }          = useAuth()
  const { data, refetch }    = useQuery({ queryKey: ['settings','webhooks'], queryFn: getWebhooks })
  const webhooks             = (data?.webhooks ?? []) as Array<{id:string;name:string;url:string}>
  const [form, setForm]      = useState({ name:'', url:'', retry_count:3 })
  const [msg,  setMsg]       = useState('')
  const addMut = useMutation({ mutationFn: () => addWebhook(form),
    onSuccess: () => { refetch(); setForm({name:'',url:'',retry_count:3}); flash(setMsg,'Webhook added',true) },
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })
  const rmMut  = useMutation({ mutationFn: removeWebhook, onSuccess: () => refetch() })
  const testMut = useMutation({ mutationFn: testWebhook,
    onSuccess: (r: { message?: string }) => flash(setMsg, r.message ?? 'Test webhook sent', true),
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })
  return (
    <div className="space-y-5 max-w-2xl">
      <h2 className="text-base font-semibold text-gray-900">Webhooks</h2>
      <Msg msg={msg} />
      {webhooks.length === 0
        ? <p className="text-sm text-gray-400">No webhooks configured.</p>
        : webhooks.map(w => (
            <div key={w.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div><p className="text-sm font-medium">{w.name}</p><p className="text-xs text-gray-400 font-mono">{w.url}</p></div>
              {isAdmin && (
                <div className="flex items-center gap-2">
                  <button className="btn-secondary text-xs py-1 px-3" onClick={()=>testMut.mutate({ webhook_id: w.id })} disabled={testMut.isPending}>
                    Test
                  </button>
                  <button className="text-red-400 hover:text-red-600 px-2 text-lg" onClick={()=>rmMut.mutate(w.id)}>x</button>
                </div>
              )}
            </div>
          ))
      }
      {isAdmin && (
        <div className="border-t pt-4 space-y-3">
          <p className="text-sm font-semibold text-gray-700">Add webhook</p>
          <div className="grid grid-cols-2 gap-3">
            <F label="Name" value={form.name} onChange={v=>setForm(f=>({...f,name:v}))} />
            <F label="URL"  value={form.url}  onChange={v=>setForm(f=>({...f,url:v}))} />
          </div>
          <div className="flex items-center gap-3">
            <button className="btn-primary" onClick={()=>addMut.mutate()} disabled={addMut.isPending||!form.name||!form.url}>Add</button>
            <button className="btn-secondary" onClick={()=>testMut.mutate({ name: form.name || 'Unsaved Webhook', url: form.url })} disabled={testMut.isPending||!form.url}>
              Test URL
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ---- Alerts -----------------------------------------------------------------
function AlertsTab() {
  const { isAdmin } = useAuth()
  const { data }    = useQuery({ queryKey: ['settings','alerts'], queryFn: getAlertConfig })
  const [cfg, setCfg] = useState({
    stream_down_enabled: true,
    audio_silence_threshold_sec: 60,
    bitrate_drop_percent: 30,
    enable_email: true,
    enable_webhook: true,
    severity_email_min: 'major',
    email_recipients: '',
  })
  const [msg, setMsg] = useState('')
  useEffect(() => { if (data) setCfg({ ...cfg, ...data }) }, [data])
  const mut = useMutation({ mutationFn: () => saveAlertConfig(cfg),
    onSuccess: () => flash(setMsg, 'Alert config saved', true),
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })
  return (
    <div className="space-y-5 max-w-xl">
      <h2 className="text-base font-semibold text-gray-900">Alert Thresholds</h2>
      <Msg msg={msg} />
      <Chk label="Enable stream down alerts" checked={cfg.stream_down_enabled}  disabled={!isAdmin} onChange={v=>setCfg(f=>({...f,stream_down_enabled:v}))} />
      <Chk label="Email delivery"            checked={cfg.enable_email}         disabled={!isAdmin} onChange={v=>setCfg(f=>({...f,enable_email:v}))} />
      <Chk label="Webhook delivery"          checked={cfg.enable_webhook}       disabled={!isAdmin} onChange={v=>setCfg(f=>({...f,enable_webhook:v}))} />
      <div className="grid grid-cols-2 gap-4">
        <F label="Audio Silence (sec)"   type="number" value={String(cfg.audio_silence_threshold_sec)} onChange={v=>setCfg(f=>({...f,audio_silence_threshold_sec:+v}))} disabled={!isAdmin} />
        <F label="Bitrate Drop (%)"      type="number" value={String(cfg.bitrate_drop_percent)}        onChange={v=>setCfg(f=>({...f,bitrate_drop_percent:+v}))}        disabled={!isAdmin} />
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Min severity for email</label>
          <select className="input" value={cfg.severity_email_min} disabled={!isAdmin} onChange={e=>setCfg(f=>({...f,severity_email_min:e.target.value}))}>
            <option value="warning">Warning (all)</option>
            <option value="major">Major + Critical</option>
            <option value="critical">Critical only</option>
          </select>
        </div>
        <F label="Email recipients (comma-separated)" value={cfg.email_recipients} onChange={v=>setCfg(f=>({...f,email_recipients:v}))} disabled={!isAdmin} placeholder="oncall@company.com,noc@company.com" />
      </div>
      {isAdmin && <button className="btn-primary" onClick={()=>mut.mutate()} disabled={mut.isPending}>Save Alerts</button>}
    </div>
  )
}

// ---- Notifications ----------------------------------------------------------
function NotificationsTab() {
  const { data }      = useQuery({ queryKey: ['settings','notifications'], queryFn: getNotifications })
  const [cfg, setCfg] = useState({ popup_enabled: true, sound_enabled: false, sound_volume: 50 })
  const [msg,  setMsg] = useState('')

  // Toast duration is stored locally (not in DB) because it only affects
  // the client browser. Read initial value from localStorage.
  const [toastSec, setToastSec] = useState(() => {
    const v = parseInt(localStorage.getItem('toast_duration') ?? '5', 10)
    return isNaN(v) ? 5 : v
  })

  useEffect(() => { if (data) setCfg(data) }, [data])

  const mut = useMutation({ mutationFn: () => saveNotifications(cfg),
    onSuccess: () => flash(setMsg, 'Saved', true),
    onError:   (e: unknown) => flash(setMsg, errMsg(e), false) })

  const saveAll = () => {
    localStorage.setItem('toast_duration', String(toastSec))
    mut.mutate()
  }

  return (
    <div className="space-y-5 max-w-sm">
      <h2 className="text-base font-semibold text-gray-900">Notifications</h2>
      <Msg msg={msg} />
      <Chk label="Pop-up toast notifications" checked={cfg.popup_enabled} onChange={v=>setCfg(f=>({...f,popup_enabled:v}))} />
      <Chk label="Alert sound"                checked={cfg.sound_enabled} onChange={v=>setCfg(f=>({...f,sound_enabled:v}))} />
      {cfg.sound_enabled && (
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Sound volume: {cfg.sound_volume}%</label>
          <input type="range" min={0} max={100} value={cfg.sound_volume}
            onChange={e=>setCfg(f=>({...f,sound_volume:+e.target.value}))} className="w-48" />
        </div>
      )}
      {/* Toast duration - stored in localStorage, applied immediately */}
      <div>
        <label className="block text-xs font-semibold text-gray-700 mb-1.5">
          Toast display duration: <span className="text-blue-600">{toastSec}s</span>
        </label>
        <input
          type="range" min={1} max={10} step={1} value={toastSec}
          onChange={e => {
            const v = +e.target.value
            setToastSec(v)
            localStorage.setItem('toast_duration', String(v))
          }}
          className="w-48"
        />
        <p className="text-xs text-gray-400 mt-1">
          How long each alert popup stays visible (1 to 10 seconds). Saves instantly.
        </p>
      </div>
      <button className="btn-primary" onClick={saveAll} disabled={mut.isPending}>Save</button>
    </div>
  )
}

// ---- Shared helpers ---------------------------------------------------------
function F({ label, value, onChange, type='text', disabled=false, placeholder='' }: {
  label:string; value:string; onChange:(v:string)=>void; type?:string; disabled?:boolean; placeholder?:string
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-700 mb-1.5">{label}</label>
      <input className="input" type={type} value={value} disabled={disabled} placeholder={placeholder}
        onChange={e=>onChange(e.target.value)} />
    </div>
  )
}
function Chk({ label, checked, onChange, disabled=false }: {
  label:string; checked:boolean; onChange:(v:boolean)=>void; disabled?:boolean
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={e=>onChange(e.target.checked)} />
      {label}
    </label>
  )
}
function Msg({ msg }: { msg:string }) {
  if (!msg) return null
  const ok = msg.includes('saved') || msg.includes('Saved') || msg.includes('sent') || msg.includes('added')
  return <div className={`text-sm rounded-lg px-4 py-2.5 ${ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>{msg}</div>
}
function flash(set:(v:string)=>void, msg:string, _ok:boolean) { set(msg); setTimeout(()=>set(''), 4000) }
function errMsg(e:unknown): string {
  const d = (e as {response?:{data?:{detail?:string}}})?.response?.data?.detail
  return typeof d === 'string' ? d : 'Request failed'
}
