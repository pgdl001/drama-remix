import { useEffect, useState } from 'react'
import { CheckCircle, XCircle } from 'lucide-react'
import api from '../lib/api'

interface Task {
  id: string
  name: string
}

interface Work {
  id: string
  task_id: string
  work_index: number
  title: string | null
  status: string
  duration: number
  file_size: number
  output_path: string | null
  review_passed: boolean | null
  created_at: string
}

export default function WorkGallery() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTask, setSelectedTask] = useState('')
  const [works, setWorks] = useState<Work[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/remix/tasks').then(res => setTasks(res.data))
  }, [])

  useEffect(() => {
    if (!selectedTask) { setWorks([]); return }
    setLoading(true)
    api.get(`/remix/tasks/${selectedTask}/works`).then(res => {
      setWorks(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [selectedTask])

  const statusBadge = (status: string, passed: boolean | null) => {
    if (passed === true) return <span className="flex items-center gap-1 text-green-600"><CheckCircle size={14} /> 已通过</span>
    if (passed === false) return <span className="flex items-center gap-1 text-red-500"><XCircle size={14} /> 未通过</span>
    const map: Record<string, string> = {
      planned: '已规划', rendering: '渲染中', rendered: '已渲染',
      reviewing: '审核中', approved: '已通过', rejected: '已拒绝', distributed: '已分发',
    }
    return <span className="text-gray-500">{map[status] || status}</span>
  }

  const fmtSize = (bytes: number) => {
    if (!bytes) return '-'
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">作品库</h2>
        <select
          value={selectedTask}
          onChange={e => setSelectedTask(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
        >
          <option value="">-- 选择任务 --</option>
          {tasks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      {!selectedTask ? (
        <div className="text-center py-20 text-gray-400">请选择一个任务查看生成的作品</div>
      ) : loading ? (
        <div className="text-gray-500">加载中...</div>
      ) : works.length === 0 ? (
        <div className="text-center py-20 text-gray-400">该任务暂无作品</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {works.map(w => (
            <div key={w.id} className="bg-white rounded-lg shadow overflow-hidden">
              <div className="aspect-video bg-gray-800 flex items-center justify-center text-gray-400 text-sm">
                {w.output_path ? (
                  <video
                    src={`/storage/outputs/${w.output_path.split(/[\\/]/).pop()}`}
                    className="w-full h-full object-cover"
                    controls
                    preload="metadata"
                  />
                ) : (
                  <span>{w.status === 'rendering' ? '渲染中...' : '暂无预览'}</span>
                )}
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm text-gray-800">{w.title || `作品 #${w.work_index}`}</span>
                  <span className="text-xs">{statusBadge(w.status, w.review_passed)}</span>
                </div>
                <div className="flex gap-4 text-xs text-gray-500">
                  <span>{w.duration > 0 ? `${w.duration.toFixed(1)}s` : '-'}</span>
                  <span>{fmtSize(w.file_size)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
