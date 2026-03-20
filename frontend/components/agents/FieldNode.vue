<template>
  <div class="field-node pl-4">
    <div class="flex items-center gap-2 py-1 hover:bg-slate-50 rounded group">
      <!-- Checkbox -->
      <input 
        type="checkbox" 
        :checked="field.selected" 
        @change="$emit('toggle', field)"
        class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5 cursor-pointer"
      />
      
      <!-- Key -->
      <span class="text-xs font-mono text-slate-700 font-medium">{{ field.key }}</span>
      
      <!-- Type Badge -->
      <span 
        class="text-[10px] px-1.5 py-0.5 rounded font-mono border"
        :class="field.type === 'array' 
          ? 'bg-purple-100 text-purple-700 border-purple-200' 
          : field.type === 'object'
          ? 'bg-blue-100 text-blue-700 border-blue-200'
          : 'bg-slate-100 text-slate-500 border-slate-200'"
      >
        {{ field.type }}
      </span>

      <!-- Example Value -->
      <span v-if="field.example !== undefined" class="ml-auto text-[10px] text-slate-400 truncate max-w-[150px] opacity-0 group-hover:opacity-100 transition-opacity">
        {{ field.example }}
      </span>
    </div>

    <!-- Children -->
    <div v-if="field.children && field.children.length > 0" class="border-l border-slate-200 ml-[7px]">
      <FieldNode 
        v-for="child in field.children" 
        :key="child.path"
        :field="child"
        @toggle="$emit('toggle', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
export interface FieldNodeData {
  path: string;
  key: string;
  type: string;
  example: any;
  selected: boolean;
  rename?: string;
  children?: FieldNodeData[];
}

defineProps<{
  field: FieldNodeData
}>()

defineEmits<{
  (e: 'toggle', field: FieldNodeData): void
}>()
</script>
