<template>
  <el-dialog :model-value="visible"
             :title="`成活复核 · ${row?.replant_no || ''}`"
             width="560px" top="10vh" destroy-on-close @update:model-value="close">
    <el-descriptions v-if="row" :column="2" border size="small" class="review-meta">
      <el-descriptions-item label="所属绿地">{{ row.green_space?.name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="植株">{{ row.plant_name }}（{{ row.plant_category_label }}）</el-descriptions-item>
      <el-descriptions-item label="规格">{{ row.spec || '-' }}</el-descriptions-item>
      <el-descriptions-item label="补植数量">{{ formatNumber(row.quantity) }} {{ row.unit_label }}</el-descriptions-item>
      <el-descriptions-item label="供苗单位">{{ row.supplier }}</el-descriptions-item>
      <el-descriptions-item label="苗木批次">{{ row.batch_no }}</el-descriptions-item>
      <el-descriptions-item label="补植日期">{{ row.replant_date }}</el-descriptions-item>
      <el-descriptions-item label="约定复核期">{{ row.review_deadline }}</el-descriptions-item>
    </el-descriptions>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" class="review-form">
      <el-form-item label="成活数量" prop="survived_quantity" :error="fieldErrors.survived_quantity">
        <el-input-number v-model="form.survived_quantity" :min="0" :max="row?.quantity || 0"
                         :precision="2" :controls="false" style="width: 100%" />
      </el-form-item>
      <el-form-item label="死亡数量">
        <el-input :model-value="deadText" disabled />
      </el-form-item>
      <el-form-item label="预计成活率">
        <el-progress :percentage="ratePercent" :stroke-width="14" :color="rateColor"
                     :format="() => rateText" />
      </el-form-item>
      <el-form-item label="复核日期" prop="reviewed_date" :error="fieldErrors.reviewed_date">
        <el-date-picker v-model="form.reviewed_date" type="date" value-format="YYYY-MM-DD"
                        placeholder="选择复核日期" style="width: 100%" />
      </el-form-item>
      <el-form-item label="死亡原因" prop="death_cause" :error="fieldErrors.death_cause">
        <el-select v-model="form.death_cause" :disabled="allSurvived" clearable
                   :placeholder="allSurvived ? '全部成活，无需填写' : '请选择死亡原因'"
                   style="width: 100%">
          <el-option v-for="item in deathCauseOptions" :key="item.value"
                     :label="item.label" :value="item.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="死亡情况说明" :error="fieldErrors.death_detail">
        <el-input v-model="form.death_detail" type="textarea" :rows="2" maxlength="2000"
                  :disabled="allSurvived" placeholder="记录死苗表现、疑似原因等（选填）" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存复核结果</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { replantingApi } from '@/api'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { formatNumber, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: deathCauseOptions } = useEnumOptions('death_cause')

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const row = ref(null)
const fieldErrors = ref({})
const form = reactive(emptyForm())

function emptyForm() {
  return {
    survived_quantity: null,
    reviewed_date: today(),
    death_cause: '',
    death_detail: '',
  }
}

const total = computed(() => Number(row.value?.quantity || 0))
const survived = computed(() => {
  const value = Number(form.survived_quantity)
  return Number.isFinite(value) ? value : null
})
const allSurvived = computed(() => survived.value !== null && survived.value >= total.value)
const deadText = computed(() => {
  if (survived.value === null) return '填写成活数量后自动计算'
  return `${formatNumber(Math.max(total.value - survived.value, 0))} ${row.value?.unit_label || ''}`
})
const ratePercent = computed(() => {
  if (survived.value === null || !total.value) return 0
  return Math.min(Math.round((survived.value / total.value) * 1000) / 10, 100)
})
const rateText = computed(() => (survived.value === null ? '待填写' : `${ratePercent.value.toFixed(1)}%`))
const rateColor = computed(() => (ratePercent.value < 85 ? '#f56c6c' : '#48a17a'))

const rules = {
  survived_quantity: [{ required: true, message: '请输入成活数量', trigger: 'blur' }],
  reviewed_date: [{ required: true, message: '请选择复核日期', trigger: 'change' }],
}

function open(source) {
  row.value = source
  Object.assign(form, emptyForm())
  if (source.survived_quantity !== null && source.survived_quantity !== undefined) {
    form.survived_quantity = source.survived_quantity
    form.reviewed_date = source.reviewed_date || today()
    form.death_cause = source.death_cause || ''
    form.death_detail = source.death_detail || ''
  }
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
    survived_quantity: form.survived_quantity,
    reviewed_date: form.reviewed_date,
    death_cause: allSurvived.value ? null : form.death_cause || null,
    death_detail: allSurvived.value ? null : form.death_detail || null,
  }
  try {
    await replantingApi.review(row.value.id, payload)
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
.review-meta {
  margin-bottom: 16px;
}

.review-form {
  margin-top: 8px;
}
</style>
