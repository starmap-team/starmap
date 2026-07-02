<script setup lang="ts">
/**
 * 技能学习进度卡片组件
 * 展示单个技能的学习状态、进度、时间估算和前置要求
 */
import { computed } from 'vue'
import { Clock, Checked, Loading as LoadingIcon } from '@element-plus/icons-vue'

interface SkillData {
  skill: string
  status: 'not_started' | 'in_progress' | 'mastered'
  progress_pct: number
  estimated_hours: number
  prerequisites: string[]
  current_level: number
  target_level: number
}

const props = defineProps<{
  skill: SkillData
}>()

const emit = defineEmits<{
  (e: 'update-status', skill: string, status: string): void
}>()

const statusConfig = computed(() => {
  const map: Record<string, { label: string; type: string; color: string }> = {
    not_started: { label: '未开始', type: 'info', color: 'var(--muted-foreground)' },
    in_progress: { label: '学习中', type: 'warning', color: 'var(--warning)' },
    mastered: { label: '已掌握', type: 'success', color: 'var(--success)' },
  }
  return map[props.skill.status] ?? map.not_started
})

const progressColor = computed(() => {
  if (props.skill.progress_pct >= 80) return 'var(--success)'
  if (props.skill.progress_pct >= 40) return 'var(--warning)'
  return 'var(--primary)'
})

const levelDots = computed(() => {
  const dots: { active: boolean; target: boolean }[] = []
  for (let i = 1; i <= 5; i++) {
    dots.push({
      active: i <= props.skill.current_level,
      target: i <= props.skill.target_level,
    })
  }
  return dots
})

function handleStatusChange(status: string) {
  emit('update-status', props.skill.skill, status)
}
</script>

<template>
  <el-card
    class="skill-card"
    shadow="hover"
    :body-style="{ padding: '16px 20px' }"
  >
    <div class="sc-top">
      <div class="sc-name">
        <span class="sc-skill-name">{{ skill.skill }}</span>
        <el-tag
          :type="statusConfig.type as any"
          size="small"
          effect="plain"
          class="sc-status-tag"
        >
          {{ statusConfig.label }}
        </el-tag>
      </div>
      <div class="sc-time">
        <el-icon :size="14">
          <Clock />
        </el-icon>
        <span>{{ skill.estimated_hours }}h</span>
      </div>
    </div>

    <div class="sc-progress-row">
      <el-progress
        :percentage="skill.progress_pct"
        :color="progressColor"
        :stroke-width="8"
        :show-text="true"
        class="sc-progress"
      />
    </div>

    <div class="sc-level">
      <span class="sc-level-label">掌握度</span>
      <div class="sc-level-dots">
        <span
          v-for="(dot, idx) in levelDots"
          :key="idx"
          class="sc-dot"
          :class="{
            'sc-dot-active': dot.active,
            'sc-dot-target': dot.target && !dot.active,
          }"
        />
      </div>
      <span class="sc-level-text">
        {{ skill.current_level }}/{{ skill.target_level }}
      </span>
    </div>

    <div
      v-if="skill.prerequisites.length"
      class="sc-prereqs"
    >
      <span class="sc-prereq-label">前置技能</span>
      <div class="sc-prereq-tags">
        <el-tag
          v-for="pre in skill.prerequisites"
          :key="pre"
          size="small"
          type="info"
          effect="plain"
        >
          {{ pre }}
        </el-tag>
      </div>
    </div>

    <div class="sc-actions">
      <el-button-group size="small">
        <el-button
          :type="skill.status === 'not_started' ? 'primary' : 'default'"
          @click="handleStatusChange('not_started')"
        >
          未开始
        </el-button>
        <el-button
          :type="skill.status === 'in_progress' ? 'warning' : 'default'"
          @click="handleStatusChange('in_progress')"
        >
          <el-icon class="mr-1">
            <LoadingIcon />
          </el-icon>
          学习中
        </el-button>
        <el-button
          :type="skill.status === 'mastered' ? 'success' : 'default'"
          @click="handleStatusChange('mastered')"
        >
          <el-icon class="mr-1">
            <Checked />
          </el-icon>
          已掌握
        </el-button>
      </el-button-group>
    </div>
  </el-card>
</template>

<style scoped>
.skill-card {
  transition: all var(--duration-normal) var(--ease-out);
  position: relative;
  overflow: hidden;
}
.skill-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.skill-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: v-bind('statusConfig.color');
  border-radius: 0 2px 2px 0;
}

.sc-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-3);
}
.sc-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.sc-skill-name {
  font-size: var(--font-size-base);
  font-weight: 700;
  color: var(--foreground);
  letter-spacing: var(--tracking-tight);
}
.sc-status-tag {
  flex-shrink: 0;
}
.sc-time {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
}

.sc-progress-row {
  margin-bottom: var(--space-3);
}
.sc-progress {
  width: 100%;
}

.sc-level {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.sc-level-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  min-width: 42px;
}
.sc-level-dots {
  display: flex;
  gap: 4px;
}
.sc-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border);
  transition: all var(--duration-fast);
}
.sc-dot-active {
  background: var(--primary);
  box-shadow: 0 0 4px color-mix(in srgb, var(--primary) 40%, transparent);
}
.sc-dot-target {
  background: transparent;
  border: 2px solid var(--primary);
  opacity: 0.5;
}
.sc-level-text {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  font-variant-numeric: tabular-nums;
  margin-left: auto;
}

.sc-prereqs {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.sc-prereq-label {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  min-width: 56px;
  flex-shrink: 0;
  padding-top: 2px;
}
.sc-prereq-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.sc-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border);
}

.mr-1 {
  margin-right: 2px;
}

@media (max-width: 640px) {
  .sc-top { flex-direction: column; gap: var(--space-1); }
  .sc-prereqs { flex-direction: column; }
  .sc-actions { justify-content: stretch; }
  .sc-actions .el-button-group { width: 100%; }
  .sc-actions .el-button-group .el-button { flex: 1; }
}
</style>
