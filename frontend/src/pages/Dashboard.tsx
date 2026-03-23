import { useEffect, useState } from 'react'
import { Film, ListChecks, CheckCircle, XCircle } from 'lucide-react'
import api from '../lib/api'

interface Stats {
  materials: number
  tasks: Record<string, number>
  works: Record<string, number>
  review: { total: number; passed: number; pass_rate: number }
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/dashboard/stats').then(res => {
      setStats(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-500">加载中...</div>

  const totalTasks = stats ? Object.values(stats.tasks).reduce((a, b) => a + b, 0) : 0
  const totalWorks = stats ? Object.values(stats.works).reduce((a, b) => a + b, 0) : 0
  const passRate = stats?.review?.pass_rate || 0

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-800 mb-6">仪表盘</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Film} label="素材总数" value={stats?.materials || 0} color="bg-blue-500" />
        <StatCard icon={ListChecks} label="任务总数" value={totalTasks} color="bg-purple-500" />
        <StatCard icon={CheckCircle} label="已生成作品" value={totalWorks} color="bg-green-500" />
        <StatCard icon={XCircle} label="过审率" value={`${(passRate * 100).toFixed(1)}%`} color="bg-orange-500" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-5">
          <h3 className="text-sm font-medium text-gray-600 mb-3">任务状态分布</h3>
          <div className="space-y-2">
            {stats && Object.entries(stats.tasks).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{statusLabel(status)}</span>
                <span className="font-medium text-gray-800">{count}</span>
              </div>
            ))}
            {(!stats || Object.keys(stats.tasks).length === 0) && (
              <p className="text-gray-400 text-sm">暂无任务</p>
            )}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-5">
          <h3 className="text-sm font-medium text-gray-600 mb-3">作品状态分布</h3>
          <div className="space-y-2">
            {stats && Object.entries(stats.works).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{statusLabel(status)}</span>
                <span className="font-medium text-gray-800">{count}</span>
              </div>
            ))}
            {(!stats || Object.keys(stats.works).length === 0) && (
              <p className="text-gray-400 text-sm">暂无作品</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number | string; color: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-5 flex items-center gap-4">
      <div className={`${color} text-white p-3 rounded-lg`}>
        <Icon size={22} />
      </div>
      <div>
        <div className="text-2xl font-bold text-gray-800">{value}</div>
        <div className="text-sm text-gray-500">{label}</div>
      </div>
    </div>
  )
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    pending: '待处理', running: '运行中', paused: '已暂停', completed: '已完成', error: '出错',
    planned: '已规划', rendering: '渲染中', rendered: '已渲染', reviewing: '审核中',
    approved: '已通过', rejected: '已拒绝', distributed: '已分发',
  }
  return map[s] || s
}
