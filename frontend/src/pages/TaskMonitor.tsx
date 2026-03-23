import { useEffect, useState } from 'react'
import { Play, Pause, RefreshCw, Trash2, CheckSquare, Square } from 'lucide-react'
import api from '../lib/api'

interface Task {
  id: string
  name: string
  material_id: string
  target_count: number
  completed_count: number
  failed_count: number
  status: string
  priority: number
  started_at: string | null
  created_at: string
}

export default function TaskMonitor() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [deleting, setDeleting] = useState(false)

  const loadTasks = () => {
    api.get('/remix/tasks').then(res => {
      setTasks(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => {
    loadTasks()
    const interval = setInterval(loadTasks, 5000)
    return () => clearInterval(interval)
  }, [])

  const startTask = async (id: string) => {
    try {
      await api.post(`/remix/tasks/${id}/start`)
      loadTasks()
    } catch (err: any) {
      alert(err.response?.data?.detail || '启动失败')
    }
  }

  const pauseTask = async (id: string) => {
    try {
      await api.post(`/remix/tasks/${id}/pause`)
      loadTasks()
    } catch (err: any) {
      alert(err.response?.data?.detail || '暂停失败')
    }
  }

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === tasks.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(tasks.map(t => t.id)))
    }
  }

  const batchDelete = async () => {
    if (selected.size === 0) return
    if (!confirm(`确定删除选中的 ${selected.size} 个任务及其所有生成文件？此操作不可恢复。`)) return
    setDeleting(true)
    try {
      const res = await api.post('/remix/tasks/batch-delete', { task_ids: Array.from(selected) })
      const data = res.data
      alert(`已删除 ${data.deleted} 个任务，清理 ${data.files_removed} 个文件`)
      setSelected(new Set())
      loadTasks()
    } catch (err: any) {
      alert(err.response?.data?.detail || '删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const statusColor = (s: string) => {
    const map: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-600',
      running: 'bg-blue-100 text-blue-700',
      paused: 'bg-yellow-100 text-yellow-700',
      completed: 'bg-green-100 text-green-700',
      error: 'bg-red-100 text-red-700',
    }
    return map[s] || 'bg-gray-100 text-gray-600'
  }

  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      pending: '待启动', running: '运行中', paused: '已暂停', completed: '已完成', error: '出错',
    }
    return map[s] || s
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">任务监控</h2>
        <div className="flex items-center gap-3">
          {selected.size > 0 && (
            <button
              onClick={batchDelete}
              disabled={deleting}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              <Trash2 size={15} />
              {deleting ? '删除中...' : `删除选中 (${selected.size})`}
            </button>
          )}
          <button onClick={loadTasks} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-800">
            <RefreshCw size={16} /> 刷新
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-gray-500">加载中...</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <p>暂无任务，前往"混剪配置"创建任务</p>
        </div>
      ) : (
        <>
          {/* Select all bar */}
          <div className="flex items-center gap-3 mb-3 px-1">
            <button onClick={toggleSelectAll} className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700">
              {selected.size === tasks.length ? <CheckSquare size={18} className="text-indigo-600" /> : <Square size={18} />}
              {selected.size === tasks.length ? '取消全选' : '全选'}
            </button>
            {selected.size > 0 && (
              <span className="text-xs text-gray-400">已选 {selected.size} / {tasks.length}</span>
            )}
          </div>

          <div className="space-y-4">
            {tasks.map(task => (
              <div key={task.id} className={`bg-white rounded-lg shadow p-5 border-2 transition-colors ${selected.has(task.id) ? 'border-indigo-400 bg-indigo-50/30' : 'border-transparent'}`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {/* Checkbox */}
                    <button onClick={() => toggleSelect(task.id)} className="text-gray-400 hover:text-indigo-600">
                      {selected.has(task.id)
                        ? <CheckSquare size={20} className="text-indigo-600" />
                        : <Square size={20} />
                      }
                    </button>
                    <h3 className="font-medium text-gray-800">{task.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(task.status)}`}>
                      {statusLabel(task.status)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    {(task.status === 'pending' || task.status === 'paused') && (
                      <button onClick={() => startTask(task.id)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700">
                        <Play size={14} /> 启动
                      </button>
                    )}
                    {task.status === 'running' && (
                      <button onClick={() => pauseTask(task.id)}
                        className="flex items-center gap-1 px-3 py-1.5 bg-yellow-500 text-white text-xs rounded-lg hover:bg-yellow-600">
                        <Pause size={14} /> 暂停
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mb-2 ml-8">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>进度: {task.completed_count} / {task.target_count}</span>
                    <span>{task.target_count > 0 ? ((task.completed_count / task.target_count) * 100).toFixed(1) : 0}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${task.target_count > 0 ? (task.completed_count / task.target_count) * 100 : 0}%` }}
                    />
                  </div>
                </div>

                <div className="flex gap-6 text-xs text-gray-500 ml-8">
                  <span>已完成: {task.completed_count}</span>
                  <span>失败: {task.failed_count}</span>
                  <span>优先级: {task.priority}</span>
                  {task.started_at && <span>开始: {new Date(task.started_at).toLocaleString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
