<template>
  <el-dialog :model-value="visible" title="成活复核登记" width="560px"
             destroy-on-close @update:model-value="close">
    <el-descriptions :column="2" border size="small" class="review-desc">
      <el-descriptions-item label="编号">{{ row?.replanting_no }}</el-descriptions-item>
      <el-descriptions-item label="苗木">{{ row?.plant_name }}（{{ row?.spec || '-' }}）</el-descriptions-item>
      <el-descriptions-item label="供苗单位">{{ row?.supplier || '-' }}</el-descriptions-item>
      <el-descriptions-item label="供苗批次">{{ row?.batch_no || '未分批' }}</el-descriptions-item>
      <el-descriptions-item label="补植日期">{{ row?.replant_date }}</el-descriptions-item>
      <el-descriptions-item label="约定复核日期">{{ row?.review_due_date || '-' }}</el-descriptions-item>
      <el-descriptions-item label="补植数量">
        {{ formatNumber(row?.quantity) }} {{ row?.unit_label }}
      </el-descriptions-item>
      <el-descriptions-item label="当前状态">
        <EnumTag group="replanting_review_status" :value="row?.review_status"
                 :label="row?.review_status_label" />
      </el-descriptions-item>
    </el-descriptions>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" class="review-form">
      <el-form-item label="复核日期" prop="reviewed_date" :error="fieldErrors.reviewed_date">
        <el-date-picker v-model="form.reviewed_date" type="date" value-format="YYYY-MM-DD"
                        placeholder="选择实际复核日期" style="width: 100%" />
      </el-form-item>
      <el-form-item label="成活数量" prop="survivor_quantity" :error="fieldErrors.survivor_quantity">
        <el-input-number v-model="form.survivor_quantity" :min="0" :max="Number(row?.quantity) || 0"
                         :precision="2" :controls="false" style="width: 100%" />
      </el-form-item>
      <el-form-item label="死亡数量">
        <el-input :model-value="deathText" disabled />
      </el-form-item>
      <el-form-item label="成活率预览">
        <el-tag :type="isLow ? 'danger' : 'success'" effect="light" size="large">
          {{ rateText }}
        </el-tag>
        <span v-if="isLow" class="low-tip">低于 {{ threshold }}%，汇总中将标记偏低</span>
      </el-form-item>
      <el-form-item v-if="hasDeath" label="主要死亡原因" prop="death_reason"
                    :error="fieldErrors.death_reason">
        <el-select v-model="form.death_reason" placeholder="请选择死亡原因" style="width: 100%">
          <el-option v-for="item in deathReasonOptions" :key="item.value"
                     :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="hasDeath" label="死亡情况说明" :error="fieldErrors.death_remark">
        <el-input v-model="form.death_remark" type="textarea" :rows="2" maxlength="2000"
                  placeholder="如：连续降雨积水、同批次苗木质量偏弱等" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交复核</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { replantingApi } from '@/api'
import EnumTag from '@/components/common/EnumTag.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { formatNumber, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: deathReasonOptions } = useEnumOptions('replanting_death_reason')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const fieldErrors = ref({})
const row = ref(null)
const form = reactive({
  reviewed_date: today(),
  survivor_quantity: null,
  death_reason: '',
  death_remark: '',
})

const rules = {
  reviewed_date: [{ required: true, message: '请选择复核日期', trigger: 'change' }],
  survivor_quantity: [{ required: true, message: '请输入成活数量', trigger: 'blur' }],
  death_reason: [{ required: true, message: '存在死亡苗木，请选择死亡原因', trigger: 'change' }],
}

const threshold = computed(() => row.value?.low_survival_threshold ?? 85)
const deathQuantity = computed(() => {
  const qty = Number(row.value?.quantity || 0)
  const alive = Number(form.survivor_quantity ?? 0)
  return Math.max(qty - alive, 0)
})
const hasDeath = computed(() => deathQuantity.value > 0)
const deathText = computed(() => `${formatNumber(deathQuantity.value)} ${row.value?.unit_label || ''}`)
const rate = computed(() => {
  const qty = Number(row.value?.quantity || 0)
  if (!qty || form.survivor_quantity === null || form.survivor_quantity === undefined) return null
  return Math.round((Number(form.survivor_quantity) / qty) * 1000) / 10
})
const rateText = computed(() => (rate.value === null ? '填写成活数量后自动核算' : `${rate.value.toFixed(1)}%`))
const isLow = computed(() => rate.value !== null && rate.value < threshold.value)

function open(target) {
  row.value = target
  Object.assign(form, {
    reviewed_date: today(),
    survivor_quantity: target.survivor_quantity ?? null,
    death_reason: target.death_reason || '',
    death_remark: target.death_remark || '',
  })
  fieldErrors.value = {}
  visible.value = true
}

function close() {
  visible.value = false
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  fieldErrors.value = {}
  const payload = {
    reviewed_date: form.reviewed_date,
    survivor_quantity: form.survivor_quantity,
    death_remark: form.death_remark || null,
  }
  if (hasDeath.value) payload.death_reason = form.death_reason
  try {
    await replantingApi.registerReview(row.value.id, payload)
    ElMessage.success('成活复核已登记')
    emit('saved')
    close()
  } catch (error) {
    fieldErrors.value = error?.details || {}
  } finally {
    submitting.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.review-desc {
  margin-bottom: 16px;
}

.review-form {
  margin-top: 8px;
}

.low-tip {
  margin-left: 10px;
  color: #f56c6c;
  font-size: 12px;
}
</style>
