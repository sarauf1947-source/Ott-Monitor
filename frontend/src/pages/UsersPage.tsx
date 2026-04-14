// frontend/src/pages/UsersPage.tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, KeyRound } from 'lucide-react'
import {
  listUsers, createUser, updateUser, deleteUser, resetUserPassword,
  type UserResponse, type UserCreate,
} from '@/services/apiV2'
import { PageHeader, PageLoader, ErrorDisplay } from '@/components/common'

type Role = 'admin' | 'operator' | 'viewer'
const ROLES: Role[] = ['admin', 'operator', 'viewer']
const ROLE_COLOR: Record<Role, string> = {
  admin:    'bg-red-100 text-red-700',
  operator: 'bg-amber-100 text-amber-700',
  viewer:   'bg-blue-100 text-blue-700',
}
const emptyForm = { username: '', email: '', full_name: '', password: '', role: 'viewer' as Role, is_active: true }

export default function UsersPage() {
  const qc = useQueryClient()
  const { data: users = [], isLoading, error } = useQuery({ queryKey: ['users'], queryFn: listUsers })

  const createMut = useMutation({ mutationFn: createUser,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); setModal(null) } })
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: object }) => updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['users'] }); setModal(null) } })
  const deleteMut = useMutation({ mutationFn: deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }) })
  const resetMut  = useMutation({
    mutationFn: ({ id, pw }: { id: number; pw: string }) => resetUserPassword(id, pw),
    onSuccess: () => setResetTarget(null) })

  const [modal,        setModal]       = useState<'create' | UserResponse | null>(null)
  const [form,         setForm]        = useState(emptyForm)
  const [resetTarget,  setResetTarget] = useState<UserResponse | null>(null)
  const [newPw,        setNewPw]       = useState('')
  const [formErr,      setFormErr]     = useState('')

  const openCreate = () => { setForm(emptyForm); setFormErr(''); setModal('create') }
  const openEdit   = (u: UserResponse) => {
    setForm({ username: u.username, email: u.email, full_name: u.full_name ?? '',
              password: '', role: u.role as Role, is_active: u.is_active })
    setFormErr(''); setModal(u)
  }

  const handleSave = async () => {
    setFormErr('')
    try {
      if (modal === 'create') {
        await createMut.mutateAsync(form as UserCreate)
      } else if (modal && typeof modal === 'object') {
        await updateMut.mutateAsync({
          id: modal.id,
          data: { email: form.email, full_name: form.full_name, role: form.role, is_active: form.is_active },
        })
      }
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFormErr(typeof msg === 'string' ? msg : 'Save failed')
    }
  }

  const handleDelete = async (u: UserResponse) => {
    if (!confirm(`Delete user "${u.username}"? This cannot be undone.`)) return
    await deleteMut.mutateAsync(u.id)
  }

  if (isLoading) return <PageLoader />
  if (error)     return <div className="p-6"><ErrorDisplay message="Failed to load users" /></div>

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="User Management"
        subtitle={`${users.length} account${users.length !== 1 ? 's' : ''}`}
        actions={<button className="btn-primary" onClick={openCreate}><Plus size={14} /> New User</button>}
      />
      <div className="flex-1 overflow-auto p-6">
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                {['Username','Full Name','Email','Role','Status','Last Login','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.username}</td>
                  <td className="px-4 py-3 text-gray-600">{u.full_name || '-'}</td>
                  <td className="px-4 py-3 text-gray-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${ROLE_COLOR[u.role as Role] ?? 'bg-gray-100 text-gray-600'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-medium ${u.is_active ? 'text-green-600' : 'text-red-500'}`}>
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <button className="btn-icon" onClick={() => openEdit(u)} title="Edit"><Pencil size={13} /></button>
                      <button className="btn-icon" onClick={() => { setResetTarget(u); setNewPw('') }} title="Reset password"><KeyRound size={13} /></button>
                      <button className="btn-icon text-red-500 hover:bg-red-50" onClick={() => handleDelete(u)} title="Delete"><Trash2 size={13} /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {modal && (
        <Modal title={modal === 'create' ? 'New User' : `Edit - ${(modal as UserResponse).username}`}
               onClose={() => setModal(null)} onSave={handleSave}
               saving={createMut.isPending || updateMut.isPending}>
          {formErr && <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-4">{formErr}</div>}
          <div className="grid grid-cols-2 gap-4">
            <F label="Username" value={form.username} disabled={modal !== 'create'} onChange={v => setForm(f => ({ ...f, username: v }))} />
            <F label="Full Name" value={form.full_name} onChange={v => setForm(f => ({ ...f, full_name: v }))} />
            <F label="Email" type="email" value={form.email} onChange={v => setForm(f => ({ ...f, email: v }))} />
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">Role</label>
              <select className="input" value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value as Role }))}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            {modal === 'create' && <F label="Password" type="password" value={form.password} onChange={v => setForm(f => ({ ...f, password: v }))} />}
            <div>
              <label className="block text-xs font-semibold text-gray-700 mb-1.5">Status</label>
              <select className="input" value={form.is_active ? 'active' : 'disabled'}
                onChange={e => setForm(f => ({ ...f, is_active: e.target.value === 'active' }))}>
                <option value="active">Active</option>
                <option value="disabled">Disabled</option>
              </select>
            </div>
          </div>
        </Modal>
      )}

      {resetTarget && (
        <Modal title={`Reset password - ${resetTarget.username}`}
               onClose={() => setResetTarget(null)}
               onSave={() => resetMut.mutateAsync({ id: resetTarget.id, pw: newPw })}
               saving={resetMut.isPending}>
          <F label="New password (min 8 chars)" type="password" value={newPw} onChange={setNewPw} />
        </Modal>
      )}
    </div>
  )
}

function F({ label, value, onChange, type = 'text', disabled = false }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; disabled?: boolean
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-700 mb-1.5">{label}</label>
      <input className="input" type={type} value={value} disabled={disabled} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function Modal({ title, children, onClose, onSave, saving }: {
  title: string; children: React.ReactNode; onClose: () => void; onSave: () => void; saving?: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">x</button>
        </div>
        <div className="p-6">{children}</div>
        <div className="flex justify-end gap-3 px-6 pb-5">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={onSave} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
        </div>
      </div>
    </div>
  )
}
