/** 可用音色列表（fallback，实际数据从 API 动态加载） */
export const VOICE_OPTIONS: Array<{ name: string; description: string }> = [
  { name: "aiden", description: "阳光美声中音，清亮通透" },
  { name: "dylan", description: "青春北京男声，清澈自然" },
  { name: "eric", description: "活泼成都男声，略带沙哑的明亮感" },
  { name: "ono_anna", description: "俏皮日式女声，轻盈灵动" },
  { name: "ryan", description: "动感男声，节奏感强" },
  { name: "serena", description: "温柔年轻女声，暖甜细腻" },
  { name: "sohee", description: "温暖韩语女声，情感丰富" },
  { name: "uncle_fu", description: "成熟男声，低沉醇厚" },
  { name: "vivian", description: "明亮年轻女声，略带锐利" },
] as const;

export type VoiceId = typeof VOICE_OPTIONS[number]["name"];