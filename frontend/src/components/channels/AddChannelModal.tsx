import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateChannel } from '@/hooks/useApi'

interface Props { onClose: () => void }
export default function AddChannelModal({ onClose }: Props) {
  const create = useCreateChannel()
  const [form, setForm] = useState({ name:'', stream_url:'', protocol:'HLS', group:'', description:'', expected_bitrate:'', expected_resolution:'' })
  const [error, setError] = useState('')
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))
  const handleSubmit = async () => {
    if (!form.name.trim() || !form.stream_url.trim()) { setError('Name and Stream URL are required'); return }
    try {
      await create.mutateAsync({ ...form, expected_bitrate: form.expected_bitrate ? parseInt(form.expected_bitrate) : null, group: form.group || null, description: form.description || null, expected_resolution: form.expected_resolution || null })
      onClose()
    } catch (e: unknown) {
      setError((e as {response?:{data?:{detail?:string}}})?.response?.data?.detail || 'Failed to create channel')
    }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Add Channel</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {[['name','Name *','text'],['stream_url','Stream URL *','text'],['group','Group','text'],['expected_bitrate','Expected Bitrate (kbps)','number'],['expected_resolution','Expected Resolution','text']].map(([k,l,t]) => (
            <div key={k}><label className="block text-xs font-semibold text-gray-700 mb-1.5">{l}</label>
              <input className="input" type={t} value={(form as Record<string,string>)[k]} onChange={e=>set(k,e.target.value)} /></div>
          ))}
          <div><label className="block text-xs font-semibold text-gray-700 mb-1.5">Protocol</label>
            <select className="input" value={form.protocol} onChange={e=>set('protocol',e.target.value)}>
              {['HLS','DASH','RTMP','OTHER'].map(p=><option key={p}>{p}</option>)}</select></div>
          {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
        </div>
        <div className="flex justify-end gap-3 px-6 pb-5">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={create.isPending}>
            {create.isPending ? 'Adding...' : 'Add Channel'}
          </button>
        </div>
      </div>
    </div>
  )
}
