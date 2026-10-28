<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsInstance, EChartsOption } from '../utils/echarts'
const props = defineProps<{ option: EChartsOption; height?: string }>()
const host = ref<HTMLElement>(); let chart: EChartsInstance | undefined; let observer: ResizeObserver | undefined; let alive=true
onMounted(async () => { const {echarts}=await import('../utils/echarts'); if (!alive||!host.value) return; const instance = echarts.init(host.value); chart = instance; instance.setOption(props.option); observer = new ResizeObserver(() => chart?.resize()); observer.observe(host.value) })
watch(() => props.option, (option) => chart?.setOption(option, true), { deep: true })
onBeforeUnmount(() => { alive=false; observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="host" class="chart-host" :style="{ height: height || '240px' }"></div></template>
