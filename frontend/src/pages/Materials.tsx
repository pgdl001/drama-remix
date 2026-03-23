import { useEffect, useState, useRef } from 'react'
import { Upload, Trash2, Search, Film, FolderOpen } from 'lucide-react'
import api from '../lib/api'

interface MaterialItem {
  id: string
  title: string
  duration: number
  file_size: number
  status: string
  created_at: string
}

interface UploadProgress {
  name: string
  progress: number  // 0-100
  status: 'uploading' | 'done' | 'error'
  error?: string
}

export default function Materials() {
  const [materials, setMaterials] = useState<MaterialItem[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadQueue, setUploadQueue] = useState<UploadProgress[]>([])
  const [importing, setImporting] = useState(false)
  const [folderDialogPath, setFolderDialogPath] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const loadMaterials = () => {
    api.get('/materials/').then(res => {
      setMaterials(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => { loadMaterials() }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    const queue: UploadProgress[] = Array.from(files).map(f => ({
      name: f.name,
      progress: 0,
      status: 'uploading' as const,
    }))
    setUploadQueue([...queue])

    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      const form = new FormData()
      form.append('file', file)
      form.append('title', file.name.replace(/\.[^.]+$/, ''))

      try {
        await api.post('/materials/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            const pct = progressEvent.total
              ? Math.round((progressEvent.loaded * 100) / progressEvent.total)
              : 0
            setUploadQueue(prev => {
              const next = [...prev]
              next[i] = { ...next[i], progress: pct }
              return next
            })
          },
        })
        setUploadQueue(prev => {
          const next = [...prev]
          next[i] = { ...next[i], progress: 100, status: 'done' }
          return next
        })
      } catch (err: any) {
        setUploadQueue(prev => {
          const next = [...prev]
          next[i] = {
            ...next[i],
            status: 'error',
            error: err.response?.data?.detail || err.message,
          }
          return next
        })
      }
    }

    loadMaterials()
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''

    // Clear queue after 4 seconds
    setTimeout(() => setUploadQueue([]), 4000)
  }

  const openFolderDialog = async () => {
    try {
      const result = await fetch('/api/materials/folder-picker-path', { method: 'POST' })
      const data = await result.json()
      if (data.path) {
        setFolderDialogPath(data.path)
      }
    } catch {
      // fallback: use prompt
      const path = window.prompt('请输入要导入的文件夹完整路径：\n（例如：C:\\Videos\\短剧）')
      if (path) setFolderDialogPath(path)
    }
  }

  const handleFolderImport = async () => {
    const rawPath = folderDialogPath.trim()
    if (!rawPath) {
      alert('请先选择文件夹')
      return
    }

    setImporting(true)
    try {
      const res = await api.post('/materials/import-folder', null, {
        params: { folder_path: rawPath },
        timeout: 300000, // 5 minutes for large folders
      })

      if (res.data.imported > 0) {
        const materialIds = res.data.items.map((item: any) => item.id)
        const bundleName = rawPath.split(/[/\\]/).pop() || '素材包'
        try {
          const bundleRes = await api.post('/bundles/', {
            name: bundleName,
            material_ids: materialIds,
          })
          alert(`导入完成！已导入 ${res.data.imported} 个视频，并自动创建素材包「${bundleName}」(ID: ${bundleRes.data.id})`)
        } catch (err: any) {
          alert(`导入完成！已导入 ${res.data.imported} 个视频。素材包创建失败(${err.response?.data?.detail || err.message})，请手动创建。`)
        }
      } else if (res.data.errors?.length > 0) {
        alert(`导入失败: ${res.data.errors[0].error}`)
      } else {
        alert('文件夹中没有找到视频文件')
      }
      loadMaterials()
      setFolderDialogPath('')
    } catch (err: any) {
      alert('导入失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setImporting(false)
    }
  }

  const handleAnalyze = async (id: string) => {
    try {
      await api.post(`/annotations/${id}/analyze`)
      alert('分析任务已启动')
      loadMaterials()
    } catch {
      alert('启动分析失败')
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该素材？')) return
    try {
      await api.delete(`/materials/${id}`)
      loadMaterials()
    } catch { /* ignore */ }
  }

  const fmtSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
  }

  const fmtDuration = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">素材管理</h2>
        <div className="flex items-center gap-2">
          <label className={`flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium cursor-pointer transition-colors ${uploading ? 'bg-gray-400' : 'bg-indigo-600 hover:bg-indigo-700'}`}>
            <Upload size={16} />
            {uploading ? '上传中...' : '上传素材'}
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              multiple
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
          </label>

          <div className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-1.5 bg-white">
            <input
              type="text"
              value={folderDialogPath}
              onChange={e => setFolderDialogPath(e.target.value)}
              placeholder={'点击右侧"浏览"选择文件夹，或手动输入路径'}
              className="text-sm text-gray-600 w-72 outline-none"
            />
            <button
              type="button"
              onClick={openFolderDialog}
              className="text-blue-600 text-sm hover:underline whitespace-nowrap cursor-pointer border-none bg-transparent"
            >
              浏览
            </button>
          </div>

          <button
            onClick={handleFolderImport}
            disabled={importing || !folderDialogPath.trim()}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium transition-colors ${importing || !folderDialogPath.trim() ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
          >
            <FolderOpen size={16} />
            {importing ? '导入中...' : '导入文件夹'}
          </button>
        </div>
      </div>

      {/* Upload progress */}
      {uploadQueue.length > 0 && (
        <div className="mb-4 space-y-2">
          {uploadQueue.map((item, i) => (
            <div key={i} className="bg-white rounded-lg shadow p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-gray-700 truncate max-w-xs">{item.name}</span>
                <span className={`text-xs font-medium ${
                  item.status === 'done' ? 'text-green-600' :
                  item.status === 'error' ? 'text-red-600' :
                  'text-indigo-600'
                }`}>
                  {item.status === 'done' ? '完成' :
                   item.status === 'error' ? `失败: ${item.error}` :
                   `${item.progress}%`}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    item.status === 'error' ? 'bg-red-500' :
                    item.status === 'done' ? 'bg-green-500' :
                    'bg-indigo-600'
                  }`}
                  style={{ width: `${item.progress}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="text-gray-500">加载中...</div>
      ) : materials.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <Film size={48} className="mx-auto mb-3 opacity-50" />
          <p>暂无素材，请上传短剧视频文件</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">标题</th>
                <th className="text-left px-4 py-3 font-medium">时长</th>
                <th className="text-left px-4 py-3 font-medium">大小</th>
                <th className="text-left px-4 py-3 font-medium">状态</th>
                <th className="text-left px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {materials.map(m => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{m.title}</td>
                  <td className="px-4 py-3 text-gray-600">{fmtDuration(m.duration)}</td>
                  <td className="px-4 py-3 text-gray-600">{fmtSize(m.file_size)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      m.status === 'ready' ? 'bg-green-100 text-green-700' :
                      m.status === 'analyzing' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {m.status === 'ready' ? '就绪' : m.status === 'analyzing' ? '分析中' : m.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 flex gap-2">
                    <button onClick={() => handleAnalyze(m.id)} className="text-indigo-600 hover:text-indigo-800" title="分析素材">
                      <Search size={16} />
                    </button>
                    <button onClick={() => handleDelete(m.id)} className="text-red-500 hover:text-red-700" title="删除">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
