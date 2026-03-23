import { useEffect, useState } from 'react'
import { Plus, Play, Save, Package, Check, Volume2, Sparkles, Type, Mic } from 'lucide-react'
import api from '../lib/api'

interface Template {
  id: string
  name: string
  hook_strategy: string
  duration_range_min: number
  duration_range_max: number
  segment_selection: string
  transition_style: string
  created_at: string
}

interface MaterialOption {
  id: string
  title: string
  status: string
  duration: number
}

interface BundleOption {
  id: string
  name: string
  episode_count: number
  total_duration: number
  total_segments: number
  status: string
}

interface EpisodeBatch {
  batch_key: string
  label: string
  material_ids: string[]
  episode_indices: number[]
}

const EDGE_VOICES = [
  { value: 'zh-CN-XiaoxiaoNeural', label: '晓晓 (女声-温柔)' },
  { value: 'zh-CN-XiaoyiNeural', label: '小艺 (女声-活泼)' },
  { value: 'zh-CN-YunxiNeural', label: '云希 (男声-自然)' },
  { value: 'zh-CN-YunyangNeural', label: '云扬 (男声-播音)' },
  { value: 'zh-CN-XiaohanNeural', label: '晓涵 (女声-成熟)' },
  { value: 'zh-CN-XiaomoNeural', label: '晓墨 (女声-正式)' },
  { value: 'zh-CN-XiaoqiuNeural', label: '晓秋 (女声-知性)' },
  { value: 'zh-CN-XiaoshuangNeural', label: '晓双 (女声-亲切)' },
  { value: 'zh-CN-XiaoyanNeural', label: '晓艳 (女声-甜美)' },
  { value: 'zh-CN-YunzeNeural', label: '云泽 (男声-稳重)' },
  { value: 'zh-CN-liaoning-YunxiaNeural', label: '辽宁小霞 (东北方言)' },
  { value: 'zh-CN-shaanxi-XiaoniNeural', label: '陕西小妮 (陕西方言)' },
  { value: 'zh-HK-HiuGaaiNeural', label: '香港小嘉 (粤语女声)' },
  { value: 'zh-HK-WanLungNeural', label: '香港云龙 (粤语男声)' },
  { value: 'zh-TW-HsiaoChenNeural', label: '台湾晓晨 (台语女声)' },
  { value: 'zh-TW-YunJheNeural', label: '台湾云喆 (台语男声)' },
]

const hookOptions = [
  { value: 'suspense', label: '悬疑钩子' },
  { value: 'question', label: '提问钩子' },
  { value: 'highlight', label: '高光钩子' },
  { value: 'emotion', label: '情感钩子' },
  { value: 'conflict', label: '冲突钩子' },
]

const transitionOptions = [
  { value: 'cut', label: '硬切' },
  { value: 'fade', label: '淡入淡出' },
  { value: 'dissolve', label: '溶解' },
  { value: 'zoom', label: '缩放' },
  { value: 'slide', label: '滑动' },
]

export default function RemixConfig() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [materials, setMaterials] = useState<MaterialOption[]>([])
  const [bundles, setBundles] = useState<BundleOption[]>([])
  const [showForm, setShowForm] = useState(false)
  const [showTaskForm, setShowTaskForm] = useState(false)

  // Template form
  const [name, setName] = useState('')
  const [hookStrategy, setHookStrategy] = useState('suspense')
  const [durationMin, setDurationMin] = useState(30)
  const [durationMax, setDurationMax] = useState(60)
  const [transitionStyle, setTransitionStyle] = useState('cut')

  // Task form
  const [taskName, setTaskName] = useState('')
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([])
  const [selectedBundleId, setSelectedBundleId] = useState('')
  const [sourceMode, setSourceMode] = useState<'materials' | 'bundle'>('materials')
  const [templateId, setTemplateId] = useState('')
  const [targetCount, setTargetCount] = useState(100)

  // V2: New feature controls - defaults ON for better experience
  const [watermarkText, setWatermarkText] = useState('')
  const [narrationEnabled, setNarrationEnabled] = useState(true)
  const [narrationVolume, setNarrationVolume] = useState(0.8)
  const [originalVolume, setOriginalVolume] = useState(0.3)
  const [effectsEnabled, setEffectsEnabled] = useState(true)

  // V3: Interspersed narration + Edge TTS
  const [narrationRatio, setNarrationRatio] = useState(30)
  const [edgeVoice, setEdgeVoice] = useState('zh-CN-XiaoxiaoNeural')

  // Episode batch selection
  const [episodeBatches, setEpisodeBatches] = useState<EpisodeBatch[]>([])
  const [selectedEpisodeBatch, setSelectedEpisodeBatch] = useState('')

  useEffect(() => {
    api.get('/remix/templates').then(res => setTemplates(res.data))
    api.get('/materials/').then(res => setMaterials(res.data))
    api.get('/bundles/').then(res => setBundles(res.data)).catch(() => {})
  }, [])

  // Load episode batches when bundle is selected
  useEffect(() => {
    if (selectedBundleId) {
      api.get(`/bundles/${selectedBundleId}/episodes?window_size=3&step=1`)
        .then(res => {
          setEpisodeBatches(res.data)
          if (res.data.length > 0) {
            setSelectedEpisodeBatch('') // all batches by default
          }
        })
        .catch(() => setEpisodeBatches([]))
    } else {
      setEpisodeBatches([])
      setSelectedEpisodeBatch('')
    }
  }, [selectedBundleId])

  const createTemplate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/remix/templates', {
        name, hook_strategy: hookStrategy,
        duration_range_min: durationMin, duration_range_max: durationMax,
        transition_style: transitionStyle,
      })
      api.get('/remix/templates').then(res => setTemplates(res.data))
      setShowForm(false)
      setName('')
    } catch (err: any) {
      alert('创建失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const toggleMaterial = (id: string) => {
    setSelectedMaterialIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const selectAll = () => {
    const readyIds = materials.filter(m => m.status === 'ready').map(m => m.id)
    setSelectedMaterialIds(readyIds)
  }

  const deselectAll = () => {
    setSelectedMaterialIds([])
  }

  const createTask = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload: any = {
        name: taskName,
        template_id: templateId || null,
        target_count: targetCount,
        watermark_text: watermarkText,
        narration_enabled: narrationEnabled,
        narration_volume: narrationVolume,
        original_volume: originalVolume,
        effects_enabled: effectsEnabled,
        narration_ratio: narrationRatio,
        edge_voice: edgeVoice,
        episode_batch: selectedEpisodeBatch || null,
      }

      if (sourceMode === 'bundle' && selectedBundleId) {
        payload.bundle_id = selectedBundleId
      } else if (sourceMode === 'materials') {
        if (selectedMaterialIds.length === 0) {
          alert('请至少选择一个素材')
          return
        }
        if (selectedMaterialIds.length === 1) {
          payload.material_id = selectedMaterialIds[0]
        } else {
          payload.material_ids = selectedMaterialIds
        }
      }

      await api.post('/remix/tasks', payload)
      const features = []
      if (narrationEnabled) features.push('AI旁白')
      if (watermarkText) features.push('水印')
      if (effectsEnabled) features.push('特效')
      const featureText = features.length > 0 ? `，已启用: ${features.join('、')}` : ''
      alert(`任务已创建并开始运行！${selectedMaterialIds.length > 1 ? '已自动打包' + selectedMaterialIds.length + '集素材' : ''}${featureText}`)
      setShowTaskForm(false)
      setTaskName('')
      setSelectedMaterialIds([])
      api.get('/bundles/').then(res => setBundles(res.data)).catch(() => {})
    } catch (err: any) {
      alert('创建失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const readyMaterials = materials.filter(m => m.status === 'ready')

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-800">混剪配置</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            <Plus size={16} /> 新建模板
          </button>
          <button
            onClick={() => setShowTaskForm(!showTaskForm)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700"
          >
            <Play size={16} /> 创建任务
          </button>
        </div>
      </div>

      {/* Create template form */}
      {showForm && (
        <form onSubmit={createTemplate} className="bg-white rounded-lg shadow p-5 mb-6 space-y-4">
          <h3 className="font-medium text-gray-800">新建混剪模板</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">模板名称</label>
              <input value={name} onChange={e => setName(e.target.value)} required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">钩子策略</label>
              <select value={hookStrategy} onChange={e => setHookStrategy(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                {hookOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最短时长 (秒)</label>
              <input type="number" value={durationMin} onChange={e => setDurationMin(+e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">最长时长 (秒)</label>
              <input type="number" value={durationMax} onChange={e => setDurationMax(+e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">转场风格</label>
              <select value={transitionStyle} onChange={e => setTransitionStyle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                {transitionOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <button type="submit" className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700">
            <Save size={16} /> 保存模板
          </button>
        </form>
      )}

      {/* Create task form */}
      {showTaskForm && (
        <form onSubmit={createTask} className="bg-white rounded-lg shadow p-5 mb-6 space-y-4">
          <h3 className="font-medium text-gray-800">创建混剪任务</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">任务名称</label>
              <input value={taskName} onChange={e => setTaskName(e.target.value)} required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">混剪模板 (可选)</label>
              <select value={templateId} onChange={e => setTemplateId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="">-- 默认配置 --</option>
                {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">目标数量</label>
              <input type="number" value={targetCount} onChange={e => setTargetCount(+e.target.value)} min={1}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
            </div>
          </div>

          {/* Source mode toggle */}
          <div>
            <label className="block text-sm text-gray-600 mb-2">素材来源</label>
            <div className="flex gap-3">
              <button type="button"
                onClick={() => setSourceMode('materials')}
                className={`px-4 py-2 text-sm rounded-lg border transition-colors ${
                  sourceMode === 'materials'
                    ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-medium'
                    : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                }`}>
                选择素材集数 (可多选)
              </button>
              {bundles.length > 0 && (
                <button type="button"
                  onClick={() => setSourceMode('bundle')}
                  className={`flex items-center gap-1 px-4 py-2 text-sm rounded-lg border transition-colors ${
                    sourceMode === 'bundle'
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-medium'
                      : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}>
                  <Package size={14} /> 使用已有素材包
                </button>
              )}
            </div>
          </div>

          {/* Materials multi-select */}
          {sourceMode === 'materials' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-gray-600">
                  选择素材 ({selectedMaterialIds.length} / {readyMaterials.length} 已选)
                  {selectedMaterialIds.length > 1 && (
                    <span className="ml-2 text-xs text-indigo-600 font-medium">
                      将自动创建素材包
                    </span>
                  )}
                </label>
                <div className="flex gap-2">
                  <button type="button" onClick={selectAll}
                    className="text-xs text-indigo-600 hover:text-indigo-800">全选</button>
                  <button type="button" onClick={deselectAll}
                    className="text-xs text-gray-500 hover:text-gray-700">清空</button>
                </div>
              </div>
              <div className="border border-gray-200 rounded-lg max-h-48 overflow-y-auto divide-y divide-gray-100">
                {readyMaterials.length === 0 ? (
                  <div className="p-4 text-center text-sm text-gray-400">
                    暂无可用素材，请先上传素材
                  </div>
                ) : readyMaterials.map(m => (
                  <label key={m.id}
                    className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors ${
                      selectedMaterialIds.includes(m.id) ? 'bg-indigo-50' : ''
                    }`}>
                    <div className={`flex items-center justify-center w-5 h-5 rounded border-2 transition-colors ${
                      selectedMaterialIds.includes(m.id)
                        ? 'bg-indigo-600 border-indigo-600'
                        : 'border-gray-300'
                    }`}>
                      {selectedMaterialIds.includes(m.id) && <Check size={12} className="text-white" />}
                    </div>
                    <input type="checkbox" className="hidden"
                      checked={selectedMaterialIds.includes(m.id)}
                      onChange={() => toggleMaterial(m.id)} />
                    <span className="flex-1 text-sm text-gray-800">{m.title}</span>
                    <span className="text-xs text-gray-400">
                      {m.duration ? `${Math.round(m.duration)}s` : ''}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Bundle select */}
          {sourceMode === 'bundle' && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">选择素材包</label>
              <select value={selectedBundleId} onChange={e => setSelectedBundleId(e.target.value)}
                required={sourceMode === 'bundle'}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="">-- 选择素材包 --</option>
                {bundles.map(b => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.episode_count}集, {Math.round(b.total_duration)}s)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* V2: Enhanced features section */}
          <div className="border-t border-gray-200 pt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">增强功能</h4>
            <div className="grid grid-cols-2 gap-4">

              {/* Watermark */}
              <div className="col-span-2">
                <label className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                  <Type size={14} /> 漂浮水印文字 (留空则不加水印)
                </label>
                <input
                  value={watermarkText}
                  onChange={e => setWatermarkText(e.target.value)}
                  placeholder="例如: @你的抖音号"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>

              {/* Narration toggle */}
              <div className="col-span-2">
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={narrationEnabled}
                    onChange={e => setNarrationEnabled(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className={`relative w-11 h-6 rounded-full transition-colors ${
                    narrationEnabled ? 'bg-indigo-600' : 'bg-gray-300'
                  }`}>
                    <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                      narrationEnabled ? 'translate-x-5' : ''
                    }`} />
                  </div>
                  <span className="flex items-center gap-1.5 text-sm text-gray-700">
                    <Volume2 size={14} /> AI旁白解说 (DeepSeek生成文案 + 语音合成)
                  </span>
                </label>
              </div>

              {/* Narration volume controls - only show when enabled */}
              {narrationEnabled && (
                <>
                  {/* V3: Narration ratio slider */}
                  <div className="col-span-2">
                    <label className="block text-sm text-gray-600 mb-1">
                      旁白占比 ({narrationRatio}%) — 控制旁白在视频中穿插的比例
                    </label>
                    <input
                      type="range" min="5" max="80" step="5"
                      value={narrationRatio}
                      onChange={e => setNarrationRatio(+e.target.value)}
                      className="w-full accent-indigo-600"
                    />
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                      <span>5% 少量点缀</span>
                      <span>30% 适中</span>
                      <span>80% 密集解说</span>
                    </div>
                  </div>

                  {/* V3: Edge TTS voice selection */}
                  <div className="col-span-2 border border-gray-300 rounded-lg p-4 bg-gray-50">
                    <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
                      <Mic size={14} /> Edge TTS 配音角色
                    </label>
                    <select
                      value={edgeVoice}
                      onChange={e => setEdgeVoice(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {EDGE_VOICES.map(v => (
                        <option key={v.value} value={v.value}>{v.label}</option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-400 mt-1">使用微软 Edge 在线语音，需要联网</p>
                  </div>

                  {/* Episode batch selection (only when bundle is selected) */}
                  {sourceMode === 'bundle' && selectedBundleId && episodeBatches.length > 0 && (
                    <div className="col-span-2 border border-blue-200 rounded-lg p-4 bg-blue-50">
                      <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
                        分集批次 — 选择要处理的集数范围
                      </label>
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedEpisodeBatch('')}
                          className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                            selectedEpisodeBatch === ''
                              ? 'bg-blue-500 text-white border-blue-500'
                              : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                          }`}
                        >
                          全部 ({episodeBatches.length}批)
                        </button>
                        {episodeBatches.map(batch => (
                          <button
                            key={batch.batch_key}
                            type="button"
                            onClick={() => setSelectedEpisodeBatch(batch.batch_key)}
                            className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                              selectedEpisodeBatch === batch.batch_key
                                ? 'bg-blue-500 text-white border-blue-500'
                                : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400'
                            }`}
                          >
                            {batch.label}
                          </button>
                        ))}
                      </div>
                      {selectedEpisodeBatch && (
                        <p className="text-xs text-gray-500 mt-2">
                          当前选择：{episodeBatches.find(b => b.batch_key === selectedEpisodeBatch)?.label}，
                          共 {episodeBatches.find(b => b.batch_key === selectedEpisodeBatch)?.material_ids.length} 集
                        </p>
                      )}
                    </div>
                  )}

                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      旁白音量 ({Math.round(narrationVolume * 100)}%)
                    </label>
                    <input
                      type="range" min="0" max="1" step="0.05"
                      value={narrationVolume}
                      onChange={e => setNarrationVolume(+e.target.value)}
                      className="w-full accent-indigo-600"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      原声音量 ({Math.round(originalVolume * 100)}%)
                    </label>
                    <input
                      type="range" min="0" max="1" step="0.05"
                      value={originalVolume}
                      onChange={e => setOriginalVolume(+e.target.value)}
                      className="w-full accent-indigo-600"
                    />
                  </div>
                </>
              )}

              {/* Effects toggle */}
              <div className="col-span-2">
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={effectsEnabled}
                    onChange={e => setEffectsEnabled(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className={`relative w-11 h-6 rounded-full transition-colors ${
                    effectsEnabled ? 'bg-amber-500' : 'bg-gray-300'
                  }`}>
                    <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                      effectsEnabled ? 'translate-x-5' : ''
                    }`} />
                  </div>
                  <span className="flex items-center gap-1.5 text-sm text-gray-700">
                    <Sparkles size={14} /> 高光特效 (在激烈/高能画面自动添加特效)
                  </span>
                </label>
              </div>

            </div>
          </div>

          <button type="submit" className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">
            <Play size={16} /> 创建任务
          </button>
        </form>
      )}

      {/* Bundles list */}
      {bundles.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden mb-6">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-medium text-gray-600 flex items-center gap-2">
              <Package size={14} /> 素材包
            </h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">名称</th>
                <th className="text-left px-4 py-3 font-medium">集数</th>
                <th className="text-left px-4 py-3 font-medium">总时长</th>
                <th className="text-left px-4 py-3 font-medium">片段数</th>
                <th className="text-left px-4 py-3 font-medium">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {bundles.map(b => (
                <tr key={b.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{b.name}</td>
                  <td className="px-4 py-3 text-gray-600">{b.episode_count}集</td>
                  <td className="px-4 py-3 text-gray-600">{Math.round(b.total_duration)}s</td>
                  <td className="px-4 py-3 text-gray-600">{b.total_segments}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                      {b.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Templates list */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-600">已有模板</h3>
        </div>
        {templates.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">暂无模板，点击"新建模板"创建</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">名称</th>
                <th className="text-left px-4 py-3 font-medium">钩子策略</th>
                <th className="text-left px-4 py-3 font-medium">时长范围</th>
                <th className="text-left px-4 py-3 font-medium">转场</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {templates.map(t => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{t.name}</td>
                  <td className="px-4 py-3 text-gray-600">{hookOptions.find(h => h.value === t.hook_strategy)?.label || t.hook_strategy}</td>
                  <td className="px-4 py-3 text-gray-600">{t.duration_range_min}s - {t.duration_range_max}s</td>
                  <td className="px-4 py-3 text-gray-600">{transitionOptions.find(tr => tr.value === t.transition_style)?.label || t.transition_style}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
