import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 用户信息 store — 存储简历上传与解析状态 */
export const useUserStore = defineStore('user', () => {
  const name = ref('')
  const resumeFile = ref<string | null>(null)
  const parsedSkills = ref<string[]>([])

  function setResume(fileName: string, skills: string[]) {
    resumeFile.value = fileName
    parsedSkills.value = skills
  }

  function clearResume() {
    name.value = ''
    resumeFile.value = null
    parsedSkills.value = []
  }

  return { name, resumeFile, parsedSkills, setResume, clearResume }
})
