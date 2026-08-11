<script setup lang="ts">
/**
 * 批量匹配模式 — extracted from MatchDiagnosis.vue (audit M14)
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useLearningStore } from '@/stores/learning'
import CompetitivenessChart from '@/components/CompetitivenessChart.vue'

const learningStore = useLearningStore()

const batchPositions = ref('')
const batchResumes = ref('')
const batchCompetitivenessPosition = ref('')

async function handleBatchMatch() {
  const positions = batchPositions.value.split('\n').map(s => s.trim()).filter(Boolean)
  const resumes = batchResumes.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (!positions.length || !resumes.length) {
    ElMessage.warning('请输入至少一个简历技能组和一个目标岗位')
    return
  }
  try {
    await learningStore.runBatchMatch(
      resumes.map((r, i) => ({
        skills: r.split(',').map(s => s.trim()),
        position: positions[i % positions.length],
      }))
    )
    ElMessage.success(`批量匹配完成，共 ${learningStore.batchResults.length} 条结果`)
  } catch {
    // error handled by store
  }
}

async function handleCompetitiveness() {
  const pos = batchCompetitivenessPosition.value.trim()
  if (!pos) {
    ElMessage.warning('请输入目标岗位名称')
    return
  }
  try {
    await learningStore.fetchCompetitiveness(pos)
  } catch {
    // error handled by store
  }
}
</script>

<template>
  <div class="batch-mode">
    <el-card shadow="hover">
      <template #header>
        <b>批量匹配</b>
      </template>
      <el-form label-position="top">
        <el-form-item label="目标岗位（每行一个）">
          <el-input
            v-model="batchPositions"
            type="textarea"
            :rows="3"
            placeholder="后端工程师&#10;前端工程师&#10;数据分析师"
          />
        </el-form-item>
        <el-form-item label="简历技能（每行一组，逗号分隔）">
          <el-input
            v-model="batchResumes"
            type="textarea"
            :rows="4"
            placeholder="Python, Django, PostgreSQL&#10;Vue, TypeScript, CSS&#10;SQL, Python, Tableau"
          />
        </el-form-item>
        <el-button
          type="primary"
          @click="handleBatchMatch"
        >
          开始批量匹配
        </el-button>
      </el-form>

      <!-- 批量匹配结果 -->
      <el-table
        v-if="learningStore.batchResults.length"
        :data="learningStore.batchResults"
        size="small"
        stripe
        class="mt-4"
      >
        <el-table-column
          prop="position_name"
          label="岗位"
          min-width="120"
        />
        <el-table-column
          prop="match_score"
          label="匹配度"
          width="100"
        >
          <template #default="{ row }">
            <b>{{ ((row.match_score ?? 0) * 100).toFixed(0) }}%</b>
          </template>
        </el-table-column>
        <el-table-column
          prop="matched_skills"
          label="匹配技能"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tag
              v-for="s in (row.matched_skills ?? [])"
              :key="s"
              size="small"
              type="success"
              class="skill-tag"
            >
              {{ s }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="gap_skills"
          label="差距技能"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tag
              v-for="s in (row.gap_skills ?? [])"
              :key="s"
              size="small"
              type="danger"
              class="skill-tag"
            >
              {{ s }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 竞争力分析 -->
    <el-card
      shadow="hover"
      class="mt-4"
    >
      <template #header>
        <b>竞争力分析</b>
      </template>
      <el-form
        label-position="top"
        :inline="true"
      >
        <el-form-item label="目标岗位">
          <el-input
            v-model="batchCompetitivenessPosition"
            placeholder="输入岗位名称"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="handleCompetitiveness"
          >
            查询竞争力
          </el-button>
        </el-form-item>
      </el-form>
      <CompetitivenessChart
        v-if="learningStore.competitiveness"
        :data="learningStore.competitiveness"
      />
    </el-card>
  </div>
</template>

<style scoped>
.batch-mode { display: flex; flex-direction: column; gap: 16px; }
.skill-tag { margin: 2px 4px; }
.mt-4 { margin-top: 16px; }
</style>
