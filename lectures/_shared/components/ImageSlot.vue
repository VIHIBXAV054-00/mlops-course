<script setup lang="ts">
// A placeholder for an image the instructor will add. Every ImageSlot needs a row in
// the deck's IMAGES.md. Replace it with the real image once the file is in public/.
// Usage: <ImageSlot id="w04-cambridge" text="Chest X-ray example from a public dataset" />
withDefaults(defineProps<{ id: string; text: string; height?: string }>(), { height: '260px' })
</script>

<template>
  <div class="image-slot" :style="{ height }">
    <div class="image-slot-id">IMAGE {{ id }}</div>
    <div class="image-slot-text">{{ text }}</div>
  </div>
</template>

<style scoped>
.image-slot {
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  border: 3px dashed #94a3b8; border-radius: 12px; color: #475569; background: #f8fafc;
  padding: 1rem; text-align: center; margin: 0.5rem auto;
}
.image-slot-id { font-family: monospace; font-size: 0.8rem; opacity: 0.7; }
.image-slot-text { font-size: 1rem; margin-top: 0.4rem; max-width: 36rem; }
</style>
