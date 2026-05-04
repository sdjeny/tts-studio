/** 可用音色列表（与服务端 _VALID_VOICES 保持一致） */
export const VOICE_OPTIONS = [
  "aiden", "dylan", "eric", "ono_anna", "ryan", "serena", "sohee", "uncle_fu", "vivian",
] as const;

export type VoiceId = typeof VOICE_OPTIONS[number];
