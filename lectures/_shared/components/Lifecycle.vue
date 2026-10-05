<script setup lang="ts">
// The Week 1 MLOps lifecycle figure, with one or more parts highlighted.
// Usage: <Lifecycle />  ·  <Lifecycle stage="build" />  ·  <Lifecycle stage="design,build" />
// Stages: plan, design, build, test, cicd, deploy, operate, monitor, development, operations
import { computed } from 'vue'
import cycleUrl from '../assets/mlops-cycle.svg?url'

const props = withDefaults(defineProps<{ stage?: string; width?: string }>(), {
  stage: '',
  width: '100%',
})

// Ellipses in the figure's own coordinates (viewBox 0 0 1236 666.8).
const SHAPES: Record<string, { cx: number; cy: number; rx: number; ry: number; rot?: number }> = {
  design: { cx: 385, cy: 170, rx: 150, ry: 62 },
  plan: { cx: 548, cy: 252, rx: 72, ry: 55, rot: 45 },
  build: { cx: 222, cy: 345, rx: 62, ry: 125 },
  test: { cx: 395, cy: 490, rx: 150, ry: 62 },
  cicd: { cx: 615, cy: 330, rx: 205, ry: 58, rot: -50 },
  deploy: { cx: 865, cy: 170, rx: 150, ry: 62 },
  operate: { cx: 1010, cy: 365, rx: 62, ry: 125 },
  monitor: { cx: 830, cy: 490, rx: 150, ry: 62 },
  development: { cx: 380, cy: 330, rx: 235, ry: 225 },
  operations: { cx: 860, cy: 330, rx: 235, ry: 225 },
}

const active = computed(() =>
  props.stage
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter(s => s in SHAPES)
    .map(s => ({ key: s, ...SHAPES[s] })),
)
const maskId = `lc-mask-${Math.random().toString(36).slice(2, 8)}`
</script>

<template>
  <div class="lifecycle" :style="{ width }">
    <img :src="cycleUrl" alt="MLOps lifecycle: plan, design, build and test in development; deploy, operate and monitor in operations; joined by CI/CD" />
    <svg v-if="active.length" viewBox="0 0 1236 666.8" class="lifecycle-overlay" aria-hidden="true">
      <defs>
        <mask :id="maskId">
          <rect x="0" y="0" width="1236" height="666.8" fill="white" />
          <ellipse v-for="a in active" :key="a.key" :cx="a.cx" :cy="a.cy" :rx="a.rx" :ry="a.ry"
            :transform="a.rot ? `rotate(${a.rot} ${a.cx} ${a.cy})` : undefined" fill="black" />
        </mask>
      </defs>
      <rect x="0" y="0" width="1236" height="666.8" fill="white" fill-opacity="0.72" :mask="`url(#${maskId})`" />
      <ellipse v-for="a in active" :key="`o-${a.key}`" :cx="a.cx" :cy="a.cy" :rx="a.rx" :ry="a.ry"
        :transform="a.rot ? `rotate(${a.rot} ${a.cx} ${a.cy})` : undefined"
        fill="none" stroke="#dc2626" stroke-width="5" stroke-dasharray="14 8" />
    </svg>
  </div>
</template>

<style scoped>
.lifecycle { position: relative; margin: 0 auto; }
.lifecycle img { display: block; width: 100%; }
.lifecycle-overlay { position: absolute; inset: 0; width: 100%; height: 100%; }
</style>
