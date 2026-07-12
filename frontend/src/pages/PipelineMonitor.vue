<script setup lang="ts">
/**
 * 数据流水线监控页 — 完整批量爬虫流
 * 展示 ETL DAG：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
 * 支持：阶段选择触发、实时SSE进度、失败重试/断点续跑、定时调度、配置调整
 */
import { RefreshRight, Setting, Timer, VideoPlay } from '@element-plus/icons-vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { ALL_STAGE_NAMES, STAGE_LABELS } from '@/stores/pipeline'
import PipelineDag from '@/components/PipelineDag.vue'
import PipelineSourcePanel from '@/components/PipelineSourcePanel.vue'
import PipelineQualityPanel from '@/components/PipelineQualityPanel.vue'
import { usePipelineMonitor } from '@/composables/usePipelineMonitor'

const {
  pipeline,
  autoRefresh,
  lastRefresh,
  loadAll,
  toggleAutoRefresh,
  sseConnected,
  handleCancelRun,
  kpiCards,
  timelineStages,
  retryingStages,
  handleRetryStage,
  handleResume,
  selectedStages,
  triggerDialogVisible,
  triggerRunType,
  openTriggerDialog,
  handleTrigger,
  scheduleDialogVisible,
  scheduleForm,
  openScheduleDialog,
  handleCreateSchedule,
  handleDeleteSchedule,
  handleTriggerSchedule,
  handleToggleSchedule,
  configDialogVisible,
  openConfigDialog,
  handleSaveConfig,
  qualityTrendOption,
  qualityTrendDir,
  isAdmin,
} = usePipelineMonitor()
</script>

<template>
  <MainLayout>
    <div class="pipeline-page animate-fade-in">
      <!-- 页面头部 -->
      <div class="page-header">
        <div>
          <h2>数据流水线监控</h2>
          <p class="page-desc">
            ETL DAG 全链路：爬虫采集 → (去重 ∥ 清洗) → 入库 → 图谱构建
            <el-tag
              v-if="sseConnected"
              size="small"
              type="success"
              effect="plain"
              class="ml-2"
            >
              SSE 实时
            </el-tag>
          </p>
        </div>
        <div class="header-actions">
          <span
            v-if="lastRefresh"
            class="last-refresh"
          >最近刷新：{{ lastRefresh }}</span>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            size="small"
            @change="toggleAutoRefresh"
          />
          <!-- LOOP-08: admin-only management controls -->
          <template v-if="isAdmin">
            <el-button
              size="small"
              type="primary"
              :icon="VideoPlay"
              :loading="pipeline.loading"
              @click="openTriggerDialog"
            >
              触发流水线
            </el-button>
            <el-button
              v-if="pipeline.pipelineStatus?.current_run?.status === 'failed'"
              size="small"
              type="warning"
              @click="handleResume"
            >
              断点续跑
            </el-button>
            <!-- Phase 1 CANCEL-03: 取消当前 running 流水线 -->
            <el-button
              v-if="pipeline.pipelineStatus?.current_run?.status === 'running'"
              size="small"
              type="danger"
              plain
              @click="handleCancelRun"
            >
              取消运行
            </el-button>
            <el-button
              size="small"
              :icon="Timer"
              @click="openScheduleDialog"
            >
              定时调度
            </el-button>
            <el-button
              size="small"
              :icon="Setting"
              @click="openConfigDialog"
            >
              配置
            </el-button>
          </template>
          <el-button
            size="small"
            :icon="RefreshRight"
            @click="loadAll"
          >
            刷新
          </el-button>
        </div>
      </div>

      <!-- 4 个 KPI 卡片 -->
      <el-row
        :gutter="16"
        class="mb-4"
      >
        <el-col
          v-for="card in kpiCards"
          :key="card.label"
          :lg="6"
          :md="12"
          :sm="24"
          class="mb-4"
        >
          <el-card
            shadow="hover"
            class="kpi-card"
          >
            <div class="kpi-inner">
              <div
                class="kpi-icon"
                :style="{ background: card.color + '18', color: card.color }"
              >
                <el-icon size="22">
                  <component :is="card.icon" />
                </el-icon>
              </div>
              <div class="kpi-body">
                <div class="kpi-label">
                  {{ card.label }}
                </div>
                <div
                  class="kpi-value"
                  :style="{ color: card.color }"
                >
                  {{ card.value }}
                </div>
                <div class="kpi-sub">
                  <span
                    v-if="card.trend === 'up'"
                    class="trend-up"
                  >▲</span>
                  <span
                    v-else-if="card.trend === 'down'"
                    class="trend-down"
                  >▼</span>
                  {{ card.sub }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 流水线 DAG 时间线视图 -->
      <PipelineDag
        :timeline-stages="timelineStages"
        :retrying-stages="retryingStages"
        :loading="pipeline.loading"
        :is-running="pipeline.pipelineStatus?.is_running ?? false"
        @retry="handleRetryStage"
      />

      <!-- 底部：数据源面板 + 数据质量监控 -->
      <el-row :gutter="16">
        <!-- 左：数据源管理面板 -->
        <el-col
          :lg="14"
          :md="24"
          class="mb-4"
        >
          <PipelineSourcePanel
            :data-sources="pipeline.dataSources"
            :loading="pipeline.loading"
          />
        </el-col>

        <!-- 右：数据质量实时监控 -->
        <el-col
          :lg="10"
          :md="24"
          class="mb-4"
        >
          <PipelineQualityPanel
            :data-quality="pipeline.dataQuality"
            :quality-trend-option="qualityTrendOption"
            :quality-trend-dir="qualityTrendDir"
            :loading="pipeline.loading"
          />
        </el-col>
      </el-row>

      <!-- 定时调度列表 -->
      <el-card
        v-if="pipeline.schedules.length"
        shadow="never"
        class="mb-4"
      >
        <template #header>
          <div class="panel-header">
            <span>定时调度</span>
            <el-button
              size="small"
              :icon="Timer"
              @click="openScheduleDialog"
            >
              新增
            </el-button>
          </div>
        </template>
        <el-table
          :data="pipeline.schedules"
          size="small"
          stripe
          empty-text="暂无数据"
        >
          <el-table-column
            prop="name"
            label="名称"
            width="140"
          />
          <el-table-column
            prop="cron_expression"
            label="Cron 表达式"
            width="140"
          />
          <el-table-column
            prop="run_type"
            label="类型"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.run_type === 'full' ? '' : 'info'"
                size="small"
              >
                {{ row.run_type === 'full' ? '全量' : '增量' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="启用"
            width="80"
          >
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                size="small"
                @change="handleToggleSchedule(row)"
              />
            </template>
          </el-table-column>
          <el-table-column
            label="上次运行"
            width="160"
          >
            <template #default="{ row }">
              {{ row.last_run_at ? new Date(row.last_run_at).toLocaleString() : '--' }}
            </template>
          </el-table-column>
          <el-table-column
            label="下次运行"
            width="160"
          >
            <template #default="{ row }">
              {{ row.next_run_at ? new Date(row.next_run_at).toLocaleString() : '--' }}
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="160"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                link
                @click="handleTriggerSchedule(row)"
              >
                立即执行
              </el-button>
              <el-button
                size="small"
                type="danger"
                link
                @click="handleDeleteSchedule(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- ── 触发流水线弹窗 ── -->
      <el-dialog
        v-model="triggerDialogVisible"
        title="触发流水线"
        width="480px"
      >
        <el-form label-width="80px">
          <el-form-item label="运行类型">
            <el-radio-group v-model="triggerRunType">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="执行阶段">
            <el-checkbox-group v-model="selectedStages">
              <el-checkbox
                v-for="name in ALL_STAGE_NAMES"
                :key="name"
                :value="name"
              >
                {{ STAGE_LABELS[name] || name }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="triggerDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :disabled="selectedStages.length === 0"
            @click="handleTrigger"
          >
            启动
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 定时调度弹窗 ── -->
      <el-dialog
        v-model="scheduleDialogVisible"
        title="创建定时调度"
        width="480px"
      >
        <el-form
          :model="scheduleForm"
          label-width="100px"
        >
          <el-form-item label="名称">
            <el-input
              v-model="scheduleForm.name"
              placeholder="如：每日增量爬取"
            />
          </el-form-item>
          <el-form-item label="Cron 表达式">
            <el-input
              v-model="scheduleForm.cron_expression"
              placeholder="0 2 * * * (每天凌晨2点)"
            />
          </el-form-item>
          <el-form-item label="运行类型">
            <el-radio-group v-model="scheduleForm.run_type">
              <el-radio value="full">
                全量
              </el-radio>
              <el-radio value="incremental">
                增量
              </el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="scheduleForm.enabled" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="scheduleDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="handleCreateSchedule"
          >
            创建
          </el-button>
        </template>
      </el-dialog>

      <!-- ── 配置弹窗 ── -->
      <el-dialog
        v-model="configDialogVisible"
        title="流水线配置"
        width="480px"
      >
        <el-form
          v-if="pipeline.config"
          label-width="120px"
        >
          <el-form-item label="阶段超时(秒)">
            <el-input-number
              v-model="pipeline.config.stage_timeout"
              :min="60"
              :max="7200"
              :step="60"
            />
          </el-form-item>
          <el-form-item label="Worker并发数">
            <el-input-number
              v-model="pipeline.config.worker_concurrency"
              :min="1"
              :max="16"
            />
          </el-form-item>
          <el-form-item label="爬取并发数">
            <el-input-number
              v-model="pipeline.config.crawl_concurrency"
              :min="1"
              :max="20"
            />
          </el-form-item>
          <el-form-item label="最大重试次数">
            <el-input-number
              v-model="pipeline.config.retry_max"
              :min="0"
              :max="10"
            />
          </el-form-item>
          <el-form-item label="重试间隔(秒)">
            <el-input-number
              v-model="pipeline.config.retry_backoff"
              :min="5"
              :max="300"
              :step="5"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="configDialogVisible = false">
            取消
          </el-button>
          <el-button
            type="primary"
            @click="handleSaveConfig"
          >
            保存
          </el-button>
        </template>
      </el-dialog>
    </div>
  </MainLayout>
</template>

<style scoped>
.pipeline-page {
  max-width: 1200px;
  margin: 0 auto;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-3);
}
.page-header h2 {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  color: var(--foreground);
  margin: 0 0 var(--space-1);
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  color: var(--muted-foreground);
  font-size: var(--font-size-sm);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.last-refresh {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
}

/* KPI 卡片 */
.kpi-card {
  cursor: default;
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  background: linear-gradient(135deg, color-mix(in srgb, var(--primary) 4%, transparent), transparent);
  transition: opacity var(--duration-normal);
}
.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.kpi-card:hover::before { opacity: 1; }
.kpi-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  position: relative;
  z-index: 1;
}
.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kpi-body {
  flex: 1;
  min-width: 0;
}
.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--muted-foreground);
  font-weight: 500;
}
.kpi-value {
  font-size: var(--font-size-3xl);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
}
.kpi-sub {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  margin-top: var(--space-1);
}
.trend-up {
  color: var(--success);
  font-weight: 600;
}
.trend-down {
  color: var(--destructive);
  font-weight: 600;
}

/* 面板头部 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mb-4 { margin-bottom: var(--space-4); }
.ml-2 { margin-left: var(--space-2); }

@media (max-width: 768px) {
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .kpi-value { font-size: var(--font-size-2xl); }
}
</style>
