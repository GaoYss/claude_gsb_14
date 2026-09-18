<template>
  <el-dialog :model-value="visible"
             :title="isEdit ? `编辑补植记录 · ${form.replant_no}` : '登记补植记录'"
             width="760px" top="6vh" destroy-on-close @update:model-value="close">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="所属绿地" prop="green_space_id" :error="fieldErrors.green_space_id">
        <GreenSpaceSelect v-model="form.green_space_id" :preset="spacePreset"
                          @update:model-value="onGreenSpaceChange" />
      </el-form-item>
      <el-form-item label="关联养护记录" :error="fieldErrors.maintenance_record_id">
        <RecordSelect v-model="form.maintenance_record_id" :green-space-id="form.green_space_id"
                      :preset="recordPreset" />
        <div class="form-hint">如本次补植源于某次养护作业，可关联对应养护记录（选填）。</div>
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="植株名称" prop="plant_name" :error="fieldErrors.plant_name">
            <el-input v-model="form.plant_name" placeholder="如：红叶石楠" maxlength="96" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="植物类别" prop="plant_category" :error="fieldErrors.plant_category">
            <el-select v-model="form.plant_category" placeholder="请选择" style="width: 100%">
              <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="规格" :error="fieldErrors.spec">
            <el-input v-model="form.spec" placeholder="如：冠幅 80-100cm" maxlength="64" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="计量单位" :error="fieldErrors.unit">
            <el-select v-model="form.unit" style="width: 100%">
              <el-option v-for="item in unitOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="补植数量" prop="quantity" :error="fieldErrors.quantity">
            <el-input-number v-model="form.quantity" :min="0.01" :max="999999" :precision="2"
                             :controls="false" placeholder="请输入数量" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="苗木来源" prop="source" :error="fieldErrors.source">
            <el-select v-model="form.source" placeholder="请选择" style="width: 100%">
              <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="供苗单位" prop="supplier" :error="fieldErrors.supplier">
            <el-input v-model="form.supplier" placeholder="如：萧山苗木合作社" maxlength="96" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="苗木批次" prop="batch_no" :error="fieldErrors.batch_no">
            <el-input v-model="form.batch_no" placeholder="如：2026春供-01" maxlength="64" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="补植日期" prop="replant_date" :error="fieldErrors.replant_date">
            <el-date-picker v-model="form.replant_date" type="date" value-format="YYYY-MM-DD"
                            placeholder="选择日期" style="width: 100%"
                            @update:model-value="onReplantDateChange" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="约定复核期" prop="review_deadline" :error="fieldErrors.review_deadline">
            <el-date-picker v-model="form.review_deadline" type="date" value-format="YYYY-MM-DD"
                            placeholder="约定复核日期" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="登记人" :error="fieldErrors.operator">
            <el-input v-model="form.operator" maxlength="64" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="备注" :error="fieldErrors.remark">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="2000" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { replantingApi } from '@/api'
import GreenSpaceSelect from '@/components/common/GreenSpaceSelect.vue'
import RecordSelect from '@/components/common/RecordSelect.vue'
import { useEnumOptions } from '@/composables/useEnumOptions'
import { addDays, today } from '@/utils/format'

const emit = defineEmits(['saved'])

const { options: categoryOptions } = useEnumOptions('plant_category')
const { options: sourceOptions } = useEnumOptions('plant_source')
const { options: unitOptions } = useEnumOptions('measure_unit')

const REVIEW_PERIOD_DAYS = 30

const formRef = ref(null)
const visible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const fieldErrors = ref({})
const spacePreset = ref(null)
const recordPreset = ref(null)
const form = reactive(emptyForm())

const isEdit = computed(() => editingId.value !== null)

const rules = {
  green_space_id: [{ required: true, message: '请选择所属绿地', trigger: 'change' }],
  plant_name: [{ required: true, message: '请输入植株名称', trigger: 'blur' }],
  plant_category: [{ required: true, message: '请选择植物类别', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入补植数量', trigger: 'blur' }],
  source: [{ required: true, message: '请选择苗木来源', trigger: 'change' }],
  supplier: [{ required: true, message: '请输入供苗单位', trigger: 'blur' }],
  batch_no: [{ required: true, message: '请输入苗木批次', trigger: 'blur' }],
  replant_date: [{ required: true, message: '请选择补植日期', trigger: 'change' }],
  review_deadline: [{ required: true, message: '请选择约定复核期', trigger: 'change' }],
}

function emptyForm() {
  const replantDate = today()
  return {
    replant_no: '',
    green_space_id: null,
    maintenance_record_id: null,
    plant_name: '',
    plant_category: 'tree',
    spec: '',
    quantity: null,
    unit: 'plant',
    source: 'nursery',
    supplier: '',
    batch_no: '',
    replant_date: replantDate,
    review_deadline: addDays(replantDate, REVIEW_PERIOD_DAYS),
    operator: '',
    remark: '',
  }
}

function open(row = null) {
  Object.assign(form, emptyForm())
  fieldErrors.value = {}
  spacePreset.value = null
  recordPreset.value = null
  editingId.value = row?.id ?? null
  if (row) {
    Object.keys(form).forEach((key) => {
      if (row[key] !== undefined && row[key] !== null) form[key] = row[key]
    })
    spacePreset.value = row.green_space || null
    recordPreset.value = row.record ? { ...row.record, id: row.maintenance_record_id } : null
  }
  visible.value = true
}

function close() {
  visible.value = false
}

function onGreenSpaceChange() {
  form.maintenance_record_id = null
  recordPreset.value = null
}

function onReplantDateChange(value) {
  // 复核期默认补植后 30 天，仍可手动调整
  if (value) form.review_deadline = addDays(value, REVIEW_PERIOD_DAYS)
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  fieldErrors.value = {}
  const payload = { ...form }
  if (!payload.replant_no) delete payload.replant_no
  if (!payload.maintenance_record_id) payload.maintenance_record_id = null
  try {
    if (isEdit.value) {
      await replantingApi.update(editingId.value, payload)
      ElMessage.success('补植记录已更新')
    } else {
      await replantingApi.create(payload)
      ElMessage.success('补植记录登记成功')
    }
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
