#!/usr/bin/env node
/**
 * iso8601.js — ISO 8601 datetime 校验(对齐 frontmatter.schema.json updated 字段 pattern)
 *
 * 用途:
 *   lint-stub.js / build-related-pages.js 等需要校验 frontmatter `updated` 字段。
 *   与 doc/schema/frontmatter.schema.json 的 `updated` pattern 保持一致:
 *     "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?(Z|[+-]\\d{2}:\\d{2})$"
 *
 * API:
 *   isIso8601(input: string): boolean
 *     严格匹配 ISO 8601 datetime pattern。
 *
 * ponytail: 不引入 npm date-fns/dayjs,纯 regex。
 */

const ISO8601_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

/**
 * 检查输入是否符合 ISO 8601 datetime 格式
 *
 * @param {string} input
 * @returns {boolean}
 */
export function isIso8601(input) {
  if (typeof input !== 'string' || !input) return false;
  return ISO8601_RE.test(input);
}

/**
 * 暴露原始正则(供 schema 校验复用)
 */
export const ISO8601_PATTERN = ISO8601_RE.source;
