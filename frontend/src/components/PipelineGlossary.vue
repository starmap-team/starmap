<script setup lang="ts">
/**
 * 术语词典
 * 帮助非技术用户理解流水线监控页面的专业术语
 */
import { Document, QuestionFilled } from '@element-plus/icons-vue'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

interface Term {
  key: string
  short: string
  desc: string
  example?: string
}

const TERMS: Term[] = [
  {
    key: 'ETL',
    short: '数据抽取-转换-加载',
    desc: '把原始数据从各个网站/API抽取出来，经过清洗加工后存入系统。',
    example: 'BOSS直聘 → 抽取 JD → 清洗 → 入库',
  },
  {
    key: 'DAG',
    short: '有向无环图 (任务依赖关系)',
    desc: '把流水线拆成多个阶段，按依赖关系排列，前一个完成才能跑下一个。',
    example: '爬虫 → (去重 ∥ 清洗) → 入库 → 图谱构建',
  },
  {
    key: 'SimHash',
    short: '文本相似度哈希',
    desc: '把两段文本转成 64 位数字, 距离近的判定为重复。批量去重 JD 用。',
    example: '"Python工程师" 和 "Python开发" 的 SimHash 距离 ≤ 3',
  },
  {
    key: 'Playwright',
    short: '浏览器自动化工具',
    desc: '模拟真实浏览器, 绕过反爬检测去抓页面。',
    example: '启动 Chromium → 设置 fingerprint → 滚动页面 → 解析 DOM',
  },
  {
    key: 'Stealth',
    short: '反检测伪装',
    desc: '让爬虫看起来像真人 (随机 UA / 鼠标轨迹 / Cookie / Webdriver 隐藏)。',
    example: 'playwright_stealth 库自动注入 stealth 脚本',
  },
  {
    key: 'Cron',
    short: '定时任务表达式',
    desc: '5 字段: 分 时 日 月 周。* 表示任意。设置流水线自动执行计划。',
    example: '"0 2 * * *" = 每天凌晨 2 点, "*/15 * * * *" = 每 15 分钟',
  },
  {
    key: '数据源',
    short: '数据来源 (平台/文件/API)',
    desc: '所有参与流水线的数据来源。包括爬虫源 (BOSS/51job) 和 API 源 (esco)。',
    example: '9 个数据源: 3 爬虫 + 3 手动/API + 3 其它类型',
  },
  {
    key: '适配器',
    short: '数据源 → 实际爬虫的映射',
    desc: '把数据源名称映射到实际可执行的爬虫函数。无适配器的源会被跳过。',
    example: '"bosszhipin" 平台 → boss_sync() 爬虫函数',
  },
  {
    key: '流水线',
    short: '一次完整 ETL 流程',
    desc: '从触发 → 爬虫 → 去重 → 清洗 → 入库 → 图谱构建的完整过程。',
    example: '一次流水线通常 30-90 分钟, 取决于爬取数据源数量',
  },
  {
    key: '阶段',
    short: '流水线中的一个步骤',
    desc: 'DAG 中的一个节点。完成或失败都会推进到下一阶段。',
    example: 'crawl / dedup / clean / import / graph_sync / timeseries',
  },
  {
    key: '增量 (incremental)',
    short: '只爬最近的新数据',
    desc: '每个源只爬 50 条 (轻量), 适合每日更新。',
    example: '今天 09:00 跑增量 → 拉到 5 个新 JD',
  },
  {
    key: '全量 (full)',
    short: '完整爬取所有数据',
    desc: '每个源爬 200 条, 适合首次建库或周更。',
    example: '每周日 02:00 跑全量 → 全部 9 个源都跑',
  },
  {
    key: '权威度',
    short: '数据源可信度评分',
    desc: '0-1 之间的分数。数据源历史表现的综合评估。≥0.8 算优质源。',
    example: 'esco 权威度 0.92 (官方标准), liepin 0.74 (猎头数据)',
  },
  {
    key: '图数据库',
    short: '存储关联关系的数据库',
    desc: '存储技能、职位、公司之间关联关系的数据库。',
    example: '节点：Python（技能）— 需要 → 高级工程师（职位）',
  },
  {
    key: 'Celery',
    short: '异步任务队列',
    desc: '后端把爬虫、抽取等耗时任务放到后台运行，不会阻塞 API。',
    example: '触发流水线 → 后台 Worker 执行爬取 → 实时推送进度',
  },
  {
    key: 'SSE',
    short: '服务器推送事件',
    desc: '后端主动推送实时进度到前端, 不需要前端轮询。',
    example: '爬虫每采 5 条 → SSE pipeline_update 事件 → 前端 DAG 实时更新',
  },
  {
    key: 'force-advance / force-reset',
    short: '强制操作 (调试用)',
    desc: '当流水线卡死时强制推进/重置。建议先 force-advance, 不行再 force-reset。',
    example: 'is_running=true 但无 stage running → 点 force-advance',
  },
]

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="术语词典 (新手指引)"
    width="780px"
    :show-close="true"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @close="close"
  >
    <div class="glossary-intro">
      <p>
        <el-icon style="vertical-align: middle">
          <QuestionFilled />
        </el-icon>
        这里是数据流水线监控页面用到的所有专业术语, 每个都附带通俗解释和使用场景。
        关闭此对话框后再次点击"新手指引"可重新打开。
      </p>
    </div>
    <el-table
      :data="TERMS"
      :show-header="false"
      stripe
      size="default"
      class="glossary-table"
    >
      <el-table-column
        prop="key"
        label="术语"
        width="140"
      >
        <template #default="{ row }">
          <span class="term-key">{{ row.key }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="short"
        label="通俗解释"
        width="180"
      >
        <template #default="{ row }">
          <span class="term-short">{{ row.short }}</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="desc"
        label="详细说明"
      >
        <template #default="{ row }">
          <div class="term-desc">
            {{ row.desc }}
            <div
              v-if="row.example"
              class="term-example"
            >
              <el-icon :size="11">
                <Document />
              </el-icon>
              {{ row.example }}
            </div>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button
        type="primary"
        @click="close"
      >
        已了解
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.glossary-intro {
  background: #f0f9ff;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: var(--space-3);
  font-size: 13px;
  color: #1e40af;
}
.glossary-intro p { margin: 0; }
.glossary-table {
  font-size: 13px;
}
.term-key {
  display: inline-block;
  padding: 2px 8px;
  background: #dbeafe;
  color: #1d4ed8;
  border-radius: 4px;
  font-weight: 700;
  font-size: 12px;
  font-family: var(--font-mono, 'Cascadia Code', monospace);
}
.term-short {
  font-weight: 600;
  color: var(--foreground);
}
.term-desc {
  color: var(--muted-foreground);
  line-height: 1.5;
}
.term-example {
  margin-top: 4px;
  padding: 4px 6px;
  background: #f8fafc;
  border-left: 2px solid #cbd5e1;
  font-size: 11px;
  font-family: var(--font-mono, 'Cascadia Code', monospace);
  color: var(--muted-foreground);
  border-radius: 0 4px 4px 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
