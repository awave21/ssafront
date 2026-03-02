import { ref } from 'vue'
import { usePromptTraining } from '~/composables/usePromptTraining'
import type { GeneratedPromptPreview, TrainingSessionRead } from '~/types/promptTraining'

export type PromptEnhancementStep =
  | 'create-session'
  | 'submit-feedback'
  | 'generate-prompt'
  | 'apply-prompt'

type EnhancePromptParams = {
  agentId: string
  sourcePrompt: string
  metaModel?: string
  onStepChange?: (step: PromptEnhancementStep) => void
}

type EnhancePromptResult =
  | {
      ok: true
      session: TrainingSessionRead
      preview: GeneratedPromptPreview
    }
  | {
      ok: false
      failedStep: PromptEnhancementStep
    }

export const useAgentPromptEnhancement = () => {
  const activeAgentId = ref<string>()

  const {
    createSession,
    submitFeedback,
    generatePrompt,
    applyPrompt,
  } = usePromptTraining(() => activeAgentId.value)

  const enhancePrompt = async (params: EnhancePromptParams): Promise<EnhancePromptResult> => {
    const { agentId, sourcePrompt, metaModel, onStepChange } = params
    activeAgentId.value = agentId

    onStepChange?.('create-session')
    const session = await createSession(metaModel ? { meta_model: metaModel } : {})
    if (!session) return { ok: false, failedStep: 'create-session' }

    onStepChange?.('submit-feedback')
    const feedback = await submitFeedback(session.id, {
      feedback_type: 'instruction',
      correction_text: sourcePrompt,
    })
    if (!feedback) return { ok: false, failedStep: 'submit-feedback' }

    onStepChange?.('generate-prompt')
    const preview = await generatePrompt(
      session.id,
      metaModel ? { meta_model: metaModel } : undefined
    )
    if (!preview) return { ok: false, failedStep: 'generate-prompt' }

    onStepChange?.('apply-prompt')
    const appliedSession = await applyPrompt(session.id, preview.generated_prompt)
    if (!appliedSession) return { ok: false, failedStep: 'apply-prompt' }

    return {
      ok: true,
      session: appliedSession,
      preview,
    }
  }

  return {
    enhancePrompt,
  }
}
