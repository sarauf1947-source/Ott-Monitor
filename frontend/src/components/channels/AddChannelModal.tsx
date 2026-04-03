import { useState } from 'react'
import { X } from 'lucide-react'
import { useCreateChannel } from '@/hooks/useApi'
import { Spinner } from '@/components/common'

interface Props { onClose: () => void }

export default function AddChannelModal({ onClose }: Props) {
  const createMutation = useCreateChannel()
  const [form, setForm] = useState({
    name: '', stream_url: '', protocol: 'HLS', group: '',
    description: '', expected_bitrate: '', expected_resolution: '',
  })
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      await createMutation.mutateAsync({
        ...form,
        expected_bitrate: form.expected_bitrate ? Number(form.expected_bitrate) : undefined,
        expected_resolution: form.expected_resolution || undefined,
        group: form.group || undefined,
        description: form.description || undefined,
      } as never)
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to create channel.'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
  }

  const field = (
    label: string,
    key: keyof typeof form,
    type = 'text',
    placeholder = '',
    required = false
  ) => (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <input
        type={type}
        className="input"
        placeholder={placeholder}
        value={form[key]}
        onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        required={required}
      />
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Add New Channel</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {field('Channel Name', 'name', 'text', 'e.g. BBC News HD', true)}
          {field('Stream URL', 'stream_url', 'url', 'https://cdn.example.com/live/stream.m3u8', true)}

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Protocol</label>
            <select
              className="input"
              value={form.protocol}
              onChange={e => setForm(f => ({ ...f, protocol: e.target.value }))}
            >
              <option value="HLS">HLS</option>
              <option value="DASH">DASH</option>
              <option value="RTMP">RTMP</option>
              <option value="OTHER">OTHER</option>
            </select>
          </div>

          {field('Group', 'group', 'text', 'e.g. Sports, News')}
          {field('Expected Bitrate (kbps)', 'expected_bitrate', 'number', '3500')}
          {field('Expected Resolution', 'expected_resolution', 'text', '1920x1080')}
          {field('Description', 'description', 'text', 'Optional notes')}

          <div className="flex gap-3 pt-2">
            <button type="button" className="btn-secondary flex-1" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary flex-1 justify-center"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? <Spinner size={14} className="text-white" /> : null}
              {createMutation.isPending ? 'Adding…' : 'Add Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
