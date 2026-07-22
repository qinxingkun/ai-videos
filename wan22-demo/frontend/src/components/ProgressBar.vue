<script setup>
defineProps({
  percent: { type: Number, default: 0 }
})
</script>

<template>
  <div class="progress">
    <span :style="{ width: percent + '%' }"></span>
  </div>
</template>
