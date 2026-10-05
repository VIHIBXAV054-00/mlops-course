<script setup lang="ts">
// A batch of data rows drawn as small squares: g = a good row, r = a bad row,
// . = a row that was removed. Spaces are ignored, so rows can be written apart.
// Usage: <DataBatch cells="ggrg gggg" :cols="4" />
import { computed } from 'vue'

const props = withDefaults(defineProps<{ cells: string; cols?: number; size?: string }>(), {
  cols: 4,
  size: '0.8rem',
})
const kinds: Record<string, string> = { g: 'good', r: 'bad', '.': 'gone' }
const list = computed(() => props.cells.replace(/\s/g, '').split('').map((c) => kinds[c] ?? 'gone'))
</script>

<template>
  <span class="data-batch" :style="{ gridTemplateColumns: `repeat(${cols}, ${size})`, gridAutoRows: size }">
    <span v-for="(kind, i) in list" :key="i" :class="['cell', kind]" />
  </span>
</template>

<style scoped>
.data-batch { display: inline-grid; gap: 3px; vertical-align: middle; }
.cell { border-radius: 2px; }
.good { background: #16a34a; }
.bad { background: #dc2626; }
.gone { border: 1.5px dashed #94a3b8; }
</style>
