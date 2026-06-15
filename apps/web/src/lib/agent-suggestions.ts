// Preset prompts grouped by the capability / tool they exercise. The composer
// shows 3 random ones as one-click buttons when the chat is empty.

export type Suggestion = { label: string; prompt: string };

export const SUGGESTIONS: Suggestion[] = [
  // get_character_detail / char-deep-dive
  { label: "“發”的繁简来源", prompt: "查一下“發”字的繁体来源和演化，简要说说" },
  { label: "深解“爱”字", prompt: "深入讲讲“爱”字：繁简来源、形声流变和文化释义" },
  { label: "“后”为何合并", prompt: "“后”字为什么是多对一合并字？" },

  // convert_text / set_convert_input + run_convert
  { label: "转成简体", prompt: "帮我把“學而時習之，不亦說乎”转成简体" },
  { label: "繁简碰撞例子", prompt: "举个繁简转换里多对一合并会出歧义的例子" },

  // search_characters / get_database_stats / get_cl_analysis
  { label: "列几个疑难合并字", prompt: "列几个繁简多对一的疑难合并字" },
  { label: "字库规模", prompt: "字库一共收录了多少字？合并字有多少？" },
  { label: "简化省了多少笔画", prompt: "繁简简化平均减少了多少笔画？" },

  // open_merge_dashboard / analyze_corpus_coverage (page operations)
  { label: "打开合并疑难总览", prompt: "帮我打开合并疑难总览看看高风险字" },
  {
    label: "审计这段语料",
    prompt:
      "用 corpus-audit 审计这段古籍的识读风险：學而時習之，不亦說乎？有朋自遠方來，不亦樂乎？",
  },

  // culture (史脉) page operation
  {
    label: "分析史记开篇",
    prompt:
      "切到史脉页，帮我分析这段：秦始皇帝者，秦莊襄王子也。莊襄王為秦質子於趙，見呂不韋姬，悅而取之，生始皇。",
  },

  // web_search / browse_page / web-lookup
  { label: "联网查甲骨文", prompt: "联网查一下甲骨文最新的研究进展，给我带引用的摘要" },
];

// Fisher-Yates shuffle on a copy, then take n. Call only on the client
// (uses Math.random) to avoid SSR/hydration mismatch.
export function pickSuggestions(n: number): Suggestion[] {
  const pool = [...SUGGESTIONS];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  return pool.slice(0, n);
}
