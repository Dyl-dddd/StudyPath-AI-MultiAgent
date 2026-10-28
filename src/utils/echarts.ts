import * as core from 'echarts/core'
import { GraphChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

core.use([GraphChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])
export const echarts = core
export type { EChartsOption }
export type EChartsInstance = ReturnType<typeof core.init>
