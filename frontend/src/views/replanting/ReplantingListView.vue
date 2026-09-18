<template>
  <div class="page">
    <PageHeader title="补植成活跟踪" description="登记苗木来源、数量、规格与供苗批次，复核期后登记成活情况，自动核算成活率并按供苗单位与批次汇总">
      <template #actions>
        <el-button type="primary" :icon="'Plus'" @click="formDialog.open()">登记补植记录</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <div class="filter-bar">
        <el-input v-model="filters.keyword" placeholder="编号 / 植株 / 供苗单位 / 批次" clearable
                  :prefix-icon="'Search'" @keyup.enter="search" @clear="search" />
        <div style="width: 200px">
          <GreenSpaceSelect v-model="filters.green_space_id" placeholder="按绿地筛选" @update:model-value="search" />
        </div>
        <el-select v-model="filters.source" placeholder="苗木来源" clearable @change="search">
          <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.plant_category" placeholder="植物类别" clearable @change="search">
          <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.review_status" placeholder="复核状态" clearable @change="search">
          <el-option label="待复核" value="pending" />
          <el-option label="已逾期" value="overdue" />
          <el-option label="已复核" value="reviewed" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" unlink-panels value-format="YYYY-MM-DD"
                        start-placeholder="补植日期起" end-placeholder="补植日期止" @change="onDateChange" />
        <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
        <el-button :icon="'RefreshLeft'" @click="reset">重置</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <StatCard label="补植记录" :value="formatNumber(summary?.total_count ?? 0)" unit="条"
                :hint="`补植数量合计 ${formatNumber(summary?.total_quantity ?? 0)}`" icon="Cherry" />
      <StatCard label="复核进度"
                :value="reviewProgress"
                unit="条"
                :hint="`待复核 ${formatNumber(summary?.pending_count ?? 0)} 条，其中逾期 ${formatNumber(summary?.overdue_count ?? 0)} 条`"
                :tone="(summary?.overdue_count ?? 0) > 0 ? 'warning' : 'default'"
                icon="View" />
      <StatCard label="总体成活率"
                :value="overallRateText"
                :unit="hasRate ? '%' : ''"
                :hint="rateHint"
                :tone="summary?.low_survival ? 'danger' : 'info'"
                icon="CircleCheck" />
      <StatCard label="成活率偏低"
                :value="formatNumber((summary?.low_supplier_count ?? 0) + (summary?.low_batch_count ?? 0))"
                unit="项"
                :hint="`供苗单位 ${formatNumber(summary?.low_supplier_count ?? 0)} 个、批次 ${formatNumber(summary?.low_batch_count ?? 0)} 个低于 ${formatNumber(summary?.threshold ?? 85)}%`"
                :tone="(summary?.low_supplier_count ?? 0) + (summary?.low_batch_count ?? 0) > 0 ? 'danger' : 'default'"
                icon="Warning" />
    </div>

    <div class="panel">
      <div class="table-toolbar">
        <span class="summary-text">
          共 <strong>{{ meta.total }}</strong> 条补植记录，
          已复核 <strong>{{ formatNumber(summary?.reviewed_count ?? 0) }}</strong> 条，
          成活 <strong>{{ formatNumber(summary?.survived_quantity ?? 0) }}</strong> /
          {{ formatNumber(summary?.reviewed_quantity ?? 0) }}
        </span>
        <el-button :icon="'Refresh'" text @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-detail">
              <span><b>苗木来源：</b>{{ row.source_label }}</span>
              <span><b>规格：</b>{{ row.spec || '-' }}</span>
              <span><b>登记人：</b>{{ row.operator || '-' }}</span>
              <span><b>关联养护记录：</b>{{ row.record ? `${row.record.record_no}（${formatDate(row.record.record_date)}）` : '未关联' }}</span>
              <span><b>复核日期：</b>{{ row.reviewed_date || '尚未复核' }}</span>
              <span v-if="row.death_cause_label"><b>死亡原因：</b>{{ row.death_cause_label }}</span>
              <span v-if="row.death_detail"><b>死亡情况：</b>{{ row.death_detail }}</span>
              <span v-if="row.remark"><b>备注：</b>{{ row.remark }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="replant_no" label="编号" width="145" />
        <el-table-column label="所属绿地" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.green_space?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="植株" width="140">
          <template #default="{ row }">
            <div>{{ row.plant_name }}</div>
            <EnumTag group="plant_category" :value="row.plant_category" :label="row.plant_category_label" />
          </template>
        </el-table-column>
        <el-table-column label="数量 / 批次" min-width="150">
          <template #default="{ row }">
            <div>{{ formatNumber(row.quantity) }} {{ row.unit_label }}</div>
            <span class="muted">{{ row.batch_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="供苗单位" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.supplier }}</template>
        </el-table-column>
        <el-table-column prop="replant_date" label="补植日期" width="100" />
        <el-table-column label="约定复核期" width="100">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.review_status === 'overdue' }">{{ row.review_deadline }}</span>
          </template>
        </el-table-column>
        <el-table-column label="复核状态" width="95">
          <template #default="{ row }">
            <el-tag :type="reviewTagType(row.review_status)" size="small">
              {{ reviewStatusText(row.review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="成活率" width="135" align="center">
          <template #default="{ row }">
            <div v-if="row.survival_rate === null" class="muted">待复核</div>
            <div v-else :class="['rate-cell', { 'rate-low': row.low_survival }]">
              <span>{{ row.survival_rate }}%</span>
              <el-tag v-if="row.low_survival" type="danger" size="small" effect="dark">偏低</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="reviewDialog.open(row)">
              {{ row.review_status === 'reviewed' ? '复核详情' : '登记复核' }}
            </el-button>
            <el-button link type="primary" @click="formDialog.open(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="pager"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="meta.total"
        :current-page="meta.page"
        :page-size="meta.page_size"
        :page-sizes="[10, 20, 50]"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="12">
        <div class="panel">
          <div class="table-toolbar">
            <span class="panel-title">按供苗单位汇总</span>
            <el-tag v-if="(summary?.low_supplier_count ?? 0) > 0" type="danger" size="small">
              {{ summary.low_supplier_count }} 个单位成活率偏低
            </el-tag>
          </div>
          <el-table :data="summary?.by_supplier || []" size="small" border :row-class-name="rowClass"
                    empty-text="暂无数据">
            <el-table-column prop="supplier" label="供苗单位" min-width="130" show-overflow-tooltip />
            <el-table-column label="补植/已复核" width="95" align="center">
              <template #default="{ row }">{{ row.count }} / {{ row.reviewed_count }}</template>
            </el-table-column>
            <el-table-column label="成活率" width="150">
              <template #default="{ row }">
                <el-progress :percentage="ratePercent(row.survival_rate)" :stroke-width="12"
                             :color="row.low_survival ? '#f56c6c' : '#48a17a'"
                             :format="() => row.survival_rate === null ? '待复核' : `${row.survival_rate}%`" />
              </template>
            </el-table-column>
            <el-table-column label="标记" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.low_survival" type="danger" size="small">偏低</el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :xs="24" :lg="12">
        <div class="panel">
          <div class="table-toolbar">
            <span class="panel-title">按苗木批次汇总</span>
            <el-tag v-if="(summary?.low_batch_count ?? 0) > 0" type="danger" size="small">
              {{ summary.low_batch_count }} 个批次成活率偏低
            </el-tag>
          </div>
          <el-table :data="summary?.by_batch || []" size="small" border :row-class-name="rowClass"
                    empty-text="暂无数据">
            <el-table-column prop="batch_no" label="苗木批次" min-width="130" show-overflow-tooltip />
            <el-table-column label="补植/已复核" width="95" align="center">
              <template #default="{ row }">{{ row.count }} / {{ row.reviewed_count }}</template>
            </el-table-column>
            <el-table-column label="成活率" width="150">
              <template #default="{ row }">
                <el-progress :percentage="ratePercent(row.survival_rate)" :stroke-width="12"
                             :color="row.low_survival ? '#f56c6c' : '#48a17a'"
                             :format="() => row.survival_rate === null ? '待复核' : `${row.survival_rate}%`" />
              </template>
            </el-table-column>
            <el-table-column label="标记" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.low_survival" type="danger" size="small">偏低</el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <ReplantingFormDialog ref="formDialog" @saved="load" />
    <ReplantReviewDialog ref="reviewDialog" @saved="load" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { replantingApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import GreenSpaceSelect from '@/components/common/GreenSpaceSelect.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import StatCard from '@/components/common/StatCard.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { useListQuery } from '@/composables/useListQuery'
import { formatDate, formatNumber } from '@/utils/format'

import ReplantingFormDialog from './ReplantingFormDialog.vue'
import ReplantReviewDialog from './ReplantReviewDialog.vue'

const route = useRoute()
const formDialog = ref(null)
const reviewDialog = ref(null)
const dateRange = ref([])

const { options: categoryOptions } = useEnumOptions('plant_category')
const { options: sourceOptions } = useEnumOptions('plant_source')

const { filters, meta, items, summary, loading, load, search, resetFilters, handlePageChange, handleSizeChange } =
  useListQuery(replantingApi.list, {
    initialFilters: {
      keyword: '',
      green_space_id: route.query.green_space_id ? Number(route.query.green_space_id) : null,
      source: '',
      plant_category: '',
      review_status: '',
      date_from: '',
      date_to: '',
    },
  })

const rateHint = computed(() => {
  const value = summary.value
  if (!value || value.survival_rate === null || value.survival_rate === undefined) {
    return '尚无已复核记录'
  }
  return `成活 ${formatNumber(value.survived_quantity)} / ${formatNumber(value.reviewed_quantity)}，低于 ${formatNumber(value.threshold)}% 标记偏低`
})

const hasRate = computed(
  () => summary.value?.survival_rate !== null && summary.value?.survival_rate !== undefined,
)
const overallRateText = computed(() => (hasRate.value ? summary.value.survival_rate : '—'))
const reviewProgress = computed(() =>
  summary.value ? `${summary.value.reviewed_count}/${summary.value.total_count}` : '-',
)

const REVIEW_STATUS_TEXT = { pending: '待复核', overdue: '已逾期', reviewed: '已复核' }
const REVIEW_TAG_TYPE = { pending: 'info', overdue: 'danger', reviewed: 'success' }

function reviewStatusText(status) {
  return REVIEW_STATUS_TEXT[status] || status
}

function reviewTagType(status) {
  return REVIEW_TAG_TYPE[status] || 'info'
}

function ratePercent(rate) {
  return rate === null || rate === undefined ? 0 : Math.min(Number(rate), 100)
}

function rowClass({ row }) {
  return row.low_survival ? 'row-low-survival' : ''
}

function onDateChange(value) {
  filters.date_from = value?.[0] || ''
  filters.date_to = value?.[1] || ''
  search()
}

function reset() {
  dateRange.value = []
  resetFilters()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确认删除补植记录「${row.replant_no}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await replantingApi.remove(row.id)
    ElMessage.success('补植记录已删除')
    await load()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
  }
}
</script>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.panel-title {
  font-weight: 600;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.text-danger {
  color: #f56c6c;
  font-weight: 600;
}

.rate-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-weight: 600;
}

.rate-low {
  color: #f56c6c;
}

.expand-detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 6px 16px;
  padding: 4px 12px;
  color: #606266;
  font-size: 13px;
}

:deep(.row-low-survival) {
  background-color: #fef0f0;
}
</style>
