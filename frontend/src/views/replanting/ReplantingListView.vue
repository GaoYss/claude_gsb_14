<template>
  <div class="page">
    <PageHeader title="补植成活跟踪" description="登记苗木来源、数量、规格与供苗批次，约定复核期后跟踪成活情况">
      <template #actions>
        <el-button type="primary" :icon="'Plus'" @click="formDialog.open()">登记补植作业</el-button>
      </template>
    </PageHeader>

    <div class="panel">
      <div class="filter-bar">
        <el-input v-model="filters.keyword" placeholder="编号 / 苗木 / 供苗单位 / 批次" clearable
                  :prefix-icon="'Search'" style="width: 240px"
                  @keyup.enter="search" @clear="search" />
        <div style="width: 200px">
          <GreenSpaceSelect v-model="filters.green_space_id" placeholder="按绿地筛选"
                            @update:model-value="search" />
        </div>
        <el-select v-model="filters.plant_category" placeholder="植物类别" clearable @change="search">
          <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.review_status" placeholder="复核状态" clearable @change="search">
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input v-model="filters.supplier" placeholder="供苗单位" clearable style="width: 150px"
                  @keyup.enter="search" @clear="search" />
        <el-input v-model="filters.batch_no" placeholder="供苗批次" clearable style="width: 140px"
                  @keyup.enter="search" @clear="search" />
        <el-date-picker v-model="dateRange" type="daterange" unlink-panels value-format="YYYY-MM-DD"
                        start-placeholder="补植日期起" end-placeholder="补植日期止" @change="onDateChange" />
        <el-checkbox v-model="filters.low_survival" :true-value="'true'" :false-value="''"
                     @change="search">仅看成活率偏低</el-checkbox>
        <el-button type="primary" :icon="'Search'" @click="search">查询</el-button>
        <el-button :icon="'RefreshLeft'" @click="reset">重置</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <StatCard label="补植记录" :value="formatNumber(summary?.total_count ?? 0)" unit="条"
                :hint="`补植数量合计 ${formatNumber(summary?.total_quantity ?? 0)}`" icon="Cherry" />
      <StatCard label="待复核 / 逾期"
                :value="`${formatNumber(summary?.pending_count ?? 0)} / ${formatNumber(summary?.overdue_count ?? 0)}`"
                :hint="`已复核 ${formatNumber(summary?.reviewed_count ?? 0)} 条`"
                :tone="(summary?.overdue_count ?? 0) > 0 ? 'danger' : 'default'"
                icon="Calendar" />
      <StatCard label="综合成活率（已复核）"
                :value="overallRate"
                :hint="`成活 ${formatNumber(summary?.survivor_quantity ?? 0)} / 死亡 ${formatNumber(summary?.death_quantity ?? 0)}`"
                :tone="summary?.low_survival_count ? 'warning' : 'info'" icon="CircleCheck" />
      <StatCard label="成活率偏低记录" :value="formatNumber(summary?.low_survival_count ?? 0)" unit="条"
                :hint="`成活率低于 ${formatNumber(summary?.low_survival_threshold ?? 85)}% 时标记`"
                :tone="(summary?.low_survival_count ?? 0) > 0 ? 'danger' : 'default'" icon="Warning" />
    </div>

    <div class="panel">
      <div class="table-toolbar">
        <span class="summary-text">
          共 <strong>{{ meta.total }}</strong> 条补植记录，
          待复核 <strong>{{ formatNumber(summary?.pending_count ?? 0) }}</strong> 条，
          逾期 <strong class="danger-text">{{ formatNumber(summary?.overdue_count ?? 0) }}</strong> 条
        </span>
        <el-button :icon="'Refresh'" text @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" border stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-detail">
              <span><b>规格：</b>{{ row.spec || '-' }}</span>
              <span><b>供苗单位：</b>{{ row.supplier || '未登记' }}</span>
              <span><b>供苗批次：</b>{{ row.batch_no || '未分批' }}</span>
              <span><b>登记人：</b>{{ row.operator || '-' }}</span>
              <span><b>关联养护记录：</b>{{ row.record ? `${row.record.record_no}（${formatDate(row.record.record_date)}）` : '未关联' }}</span>
              <span v-if="row.review_status === 'done'"><b>复核日期：</b>{{ row.reviewed_date }}</span>
              <span v-if="row.review_status === 'done'"><b>死亡原因：</b>{{ row.death_reason_label || '全部成活' }}</span>
              <span v-if="row.death_remark"><b>死亡说明：</b>{{ row.death_remark }}</span>
              <span><b>登记时间：</b>{{ formatDateTime(row.created_at) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="replanting_no" label="编号" width="150" />
        <el-table-column label="所属绿地" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.green_space?.name || '-' }}</template>
        </el-table-column>
        <el-table-column label="苗木" width="140">
          <template #default="{ row }">
            <div>{{ row.plant_name }}</div>
            <EnumTag group="plant_category" :value="row.plant_category" :label="row.plant_category_label" />
          </template>
        </el-table-column>
        <el-table-column label="补植数量" width="120" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.quantity) }} {{ row.unit_label }}
          </template>
        </el-table-column>
        <el-table-column prop="supplier" label="供苗单位" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.supplier || '-' }}</template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次" width="120">
          <template #default="{ row }">{{ row.batch_no || '-' }}</template>
        </el-table-column>
        <el-table-column prop="replant_date" label="补植日期" width="105" />
        <el-table-column label="约定复核" width="115">
          <template #default="{ row }">
            <span :class="{ 'danger-text': row.review_status === 'overdue' }">
              {{ formatDate(row.review_due_date) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="复核状态" width="100">
          <template #default="{ row }">
            <EnumTag group="replanting_review_status" :value="row.review_status"
                    :label="row.review_status_label" />
          </template>
        </el-table-column>
        <el-table-column label="成活率" width="120" align="center">
          <template #default="{ row }">
            <div v-if="row.survival_rate !== null"
                 :class="['rate-cell', row.low_survival ? 'rate-low' : 'rate-ok']">
              {{ formatPercent(row.survival_rate) }}
              <el-icon v-if="row.low_survival" title="成活率偏低"><WarningFilled /></el-icon>
            </div>
            <span v-else class="rate-pending">待复核</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="reviewDialog.open(row)">
              {{ row.review_status === 'done' ? '复核结果' : '登记复核' }}
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

    <div class="summary-grid">
      <div class="panel">
        <div class="table-toolbar">
          <span class="panel-title">按供苗单位汇总</span>
          <span class="summary-text">成活率低于 {{ formatNumber(summary?.low_survival_threshold ?? 85) }}% 自动标记</span>
        </div>
        <el-table :data="summary?.by_supplier || []" size="small" border
                  :row-class-name="supplierRowClass" empty-text="暂无数据">
          <el-table-column prop="label" label="供苗单位" min-width="140" show-overflow-tooltip />
          <el-table-column prop="count" label="记录" width="70" align="right" />
          <el-table-column label="补植数量" width="100" align="right">
            <template #default="{ row }">{{ formatNumber(row.quantity) }}</template>
          </el-table-column>
          <el-table-column prop="reviewed_count" label="已复核" width="80" align="right" />
          <el-table-column label="成活率" min-width="170">
            <template #default="{ row }">
              <div class="rate-bar">
                <el-progress :percentage="ratePercent(row.survival_rate)" :stroke-width="12"
                             :color="row.low_survival ? '#f56c6c' : '#48a17a'"
                             :format="() => row.survival_rate === null ? '待复核' : formatPercent(row.survival_rate)" />
                <el-tag v-if="row.low_survival" type="danger" size="small" effect="dark">偏低</el-tag>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="panel">
        <div class="table-toolbar">
          <span class="panel-title">按供苗批次汇总</span>
          <span class="summary-text">同一单位不同批次分别核算</span>
        </div>
        <el-table :data="summary?.by_batch || []" size="small" border max-height="360"
                  :row-class-name="supplierRowClass" empty-text="暂无数据">
          <el-table-column prop="label" label="供苗批次" min-width="120" show-overflow-tooltip />
          <el-table-column prop="supplier" label="供苗单位" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.supplier || '未登记' }}</template>
          </el-table-column>
          <el-table-column label="补植数量" width="90" align="right">
            <template #default="{ row }">{{ formatNumber(row.quantity) }}</template>
          </el-table-column>
          <el-table-column label="成活率" width="100" align="center">
            <template #default="{ row }">
              <span v-if="row.survival_rate === null" class="rate-pending">待复核</span>
              <span v-else :class="row.low_survival ? 'rate-low' : 'rate-ok'">
                {{ formatPercent(row.survival_rate) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <ReplantingFormDialog ref="formDialog" @saved="load" />
    <ReplantingReviewDialog ref="reviewDialog" @saved="load" />
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
import { formatDate, formatDateTime, formatNumber, formatPercent } from '@/utils/format'

import ReplantingFormDialog from './ReplantingFormDialog.vue'
import ReplantingReviewDialog from './ReplantingReviewDialog.vue'

const route = useRoute()
const formDialog = ref(null)
const reviewDialog = ref(null)
const dateRange = ref([])

const { options: categoryOptions } = useEnumOptions('plant_category')
const { options: statusOptions } = useEnumOptions('replanting_review_status')

const { filters, meta, items, summary, loading, load, search, resetFilters,
        handlePageChange, handleSizeChange } = useListQuery(replantingApi.list, {
  initialFilters: {
    keyword: '',
    green_space_id: route.query.green_space_id ? Number(route.query.green_space_id) : null,
    plant_category: '',
    review_status: '',
    supplier: '',
    batch_no: '',
    low_survival: '',
    date_from: '',
    date_to: '',
  },
})

const overallRate = computed(() => {
  const rate = summary.value?.survival_rate
  return rate === null || rate === undefined ? '-' : formatPercent(rate)
})

function ratePercent(rate) {
  return rate === null || rate === undefined ? 0 : Math.min(Number(rate), 100)
}

function supplierRowClass({ row }) {
  return row.low_survival ? 'low-survival-row' : ''
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
    await ElMessageBox.confirm(`确认删除补植记录「${row.replanting_no}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await replantingApi.remove(row.id)
    ElMessage.success('补植作业记录已删除')
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

.summary-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}

.danger-text,
.rate-low {
  color: #f56c6c;
  font-weight: 600;
}

.rate-ok {
  color: #48a17a;
  font-weight: 600;
}

.rate-pending {
  color: #909399;
  font-size: 12px;
}

.rate-cell {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.rate-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.expand-detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 6px 16px;
  padding: 4px 12px;
  color: #606266;
  font-size: 13px;
}

:deep(.low-survival-row) {
  background-color: #fef0f0;
}
</style>
