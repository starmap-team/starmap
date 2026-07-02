<script setup lang="ts">
import { ref, computed } from "vue"
import { Search } from "@element-plus/icons-vue"
import { useGraphStore } from "@/stores/graph"

const emit = defineEmits<{
  nodeSelected: [id: string, name: string, type: string]
}>()

const graphStore = useGraphStore()
const searchKeyword = ref("")
const showSearchDropdown = ref(false)
const searchHighlightIndex = ref(-1)

const searchResults = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return []
  const seen = new Set<string>()
  const results: { id: string; name: string; type: string }[] = []

  // 1. 搜索已加载的领域
  for (const d of graphStore.domains) {
    if (d.name.toLowerCase().includes(kw) && !seen.has(d.id)) {
      seen.add(d.id)
      results.push({ id: d.id, name: d.name, type: "领域" })
    }
  }

  // 2. 搜索已加载的节点（allNodes 已通过 fetchKAPositions 逐步加载）
  for (const n of graphStore.allNodes) {
    if (n.properties.name.toLowerCase().includes(kw) && !seen.has(n.id)) {
      seen.add(n.id)
      const label = n.labels[0] === "Position" ? "岗位" : n.labels[0] === "Skill" ? "技能" : n.labels[0]
      results.push({ id: n.id, name: n.properties.name, type: label })
    }
  }

  results.sort((a, b) => {
    const ae = a.name.toLowerCase() === kw ? 0 : 1, be = b.name.toLowerCase() === kw ? 0 : 1
    return ae - be
  })
  return results.slice(0, 10)
})

function onSearchInput() {
  showSearchDropdown.value = searchResults.value.length > 0 && searchKeyword.value.trim().length > 0
  searchHighlightIndex.value = -1
}
function onSearchKeydown(e: KeyboardEvent) {
  if (e.key === "ArrowDown") { e.preventDefault(); searchHighlightIndex.value = searchHighlightIndex.value < searchResults.value.length - 1 ? searchHighlightIndex.value + 1 : 0 }
  else if (e.key === "ArrowUp") { e.preventDefault(); searchHighlightIndex.value = searchHighlightIndex.value > 0 ? searchHighlightIndex.value - 1 : searchResults.value.length - 1 }
  else if (e.key === "Enter") { e.preventDefault(); if (searchHighlightIndex.value >= 0) selectResult(searchResults.value[searchHighlightIndex.value]); else if (searchResults.value.length) selectResult(searchResults.value[0]) }
  else if (e.key === "Escape") { searchKeyword.value = ""; showSearchDropdown.value = false }
}
function selectResult(r: { id: string; name: string; type: string }) {
  showSearchDropdown.value = false
  searchHighlightIndex.value = -1
  searchKeyword.value = ""
  emit("nodeSelected", r.id, r.name, r.type)
}
function onSearchBlur() { setTimeout(() => { showSearchDropdown.value = false }, 200) }
</script>

<template>
  <div class="search-bar glass border-glow">
    <div class="search-inner">
      <el-icon
        size="16"
        color="var(--muted-foreground)"
      >
        <Search />
      </el-icon>
      <div class="search-input-wrapper">
        <input
          v-model="searchKeyword"
          class="search-input"
          placeholder="搜索岗位、技能、领域..."
          @input="onSearchInput"
          @keydown.down.prevent="onSearchKeydown"
          @keydown.up.prevent="onSearchKeydown"
          @keydown.enter.prevent="onSearchKeydown"
          @blur="onSearchBlur"
          @focus="onSearchInput"
        >
        <transition name="fade">
          <div
            v-if="showSearchDropdown"
            class="search-dropdown glass"
          >
            <div
              v-for="(r, idx) in searchResults"
              :key="r.id"
              class="search-item"
              :class="{ highlighted: idx === searchHighlightIndex }"
              @mousedown.prevent="selectResult(r)"
            >
              <span
                class="si-dot"
                :style="{ background: r.type === '领域' ? 'var(--chart-3)' : r.type === '岗位' ? 'var(--chart-1)' : 'var(--success)' }"
              />
              <span class="si-name">{{ r.name }}</span>
              <span class="si-type">{{ r.type }}</span>
            </div>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-bar {
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  padding: var(--space-2-5) var(--space-4);
  transition: all var(--duration-normal) var(--ease-out);
  box-shadow: var(--shadow-xs);
}
.search-bar:focus-within {
  border-color: color-mix(in srgb, var(--primary) 40%, var(--border));
  box-shadow: var(--shadow-glow);
}
.search-inner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.search-input-wrapper {
  flex: 1;
  position: relative;
}
.search-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--font-size-sm);
  color: var(--foreground);
  font-family: var(--font-sans);
  letter-spacing: -0.01em;
}
.search-input::placeholder { color: var(--muted-foreground); }
.search-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  z-index: var(--z-dropdown);
  max-height: 280px;
  overflow-y: auto;
}
.search-item {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  padding: var(--space-2-5) var(--space-3);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: background var(--duration-fast);
}
.search-item:hover,
.search-item.highlighted {
  background: var(--primary-ghost);
}
.si-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.si-name {
  flex: 1;
  color: var(--foreground);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.si-type {
  font-size: var(--font-size-xs);
  color: var(--muted-foreground);
  flex-shrink: 0;
}
</style>
