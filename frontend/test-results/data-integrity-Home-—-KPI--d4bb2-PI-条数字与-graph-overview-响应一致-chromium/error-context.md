# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: data-integrity.spec.ts >> Home — KPI 数据 vs 后端 >> KPI 条数字与 /graph/overview 响应一致
- Location: e2e\data-integrity.spec.ts:43:3

# Error details

```
Error: API call matching /graph/overview not received within 15000ms
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - complementary [ref=e4]:
    - link "StarMap 星图" [ref=e6] [cursor=pointer]:
      - /url: /
      - img [ref=e8]
      - generic [ref=e15]:
        - generic [ref=e16]: StarMap
        - generic [ref=e17]: 星图
    - button "折叠侧栏" [ref=e18] [cursor=pointer]:
      - img [ref=e20]
    - navigation [ref=e22]:
      - generic [ref=e23]:
        - generic [ref=e24]: 数据
        - generic [ref=e25] [cursor=pointer]:
          - img [ref=e28]
          - generic [ref=e31]: 全景图谱
        - generic [ref=e33] [cursor=pointer]:
          - img [ref=e36]
          - generic [ref=e38]: 岗位列表
        - generic [ref=e39] [cursor=pointer]:
          - img [ref=e42]
          - generic [ref=e44]: 数据流水线
        - generic [ref=e45] [cursor=pointer]:
          - img [ref=e48]
          - generic [ref=e52]: 数据源管理
      - generic [ref=e53]:
        - generic [ref=e54]: 工具
        - generic [ref=e55] [cursor=pointer]:
          - img [ref=e58]
          - generic [ref=e60]: 匹配诊断
        - generic [ref=e61] [cursor=pointer]:
          - img [ref=e64]
          - generic [ref=e66]: JD 抽取
        - generic [ref=e67] [cursor=pointer]:
          - img [ref=e70]
          - generic [ref=e72]: 闭环演示
        - generic [ref=e73] [cursor=pointer]:
          - img [ref=e76]
          - generic [ref=e79]: 学习中心
      - generic [ref=e80]:
        - generic [ref=e81]: 洞察
        - generic [ref=e82] [cursor=pointer]:
          - img [ref=e85]
          - generic [ref=e89]: 数据大屏
        - generic [ref=e90] [cursor=pointer]:
          - img [ref=e93]
          - generic [ref=e95]: 演化看板
        - generic [ref=e96] [cursor=pointer]:
          - img [ref=e99]
          - generic [ref=e101]: 图谱质量
      - generic [ref=e103]: 系统
    - button "深色模式" [ref=e105] [cursor=pointer]:
      - img [ref=e107]
      - generic [ref=e110]: 深色模式
  - generic [ref=e111]:
    - generic [ref=e113]:
      - generic [ref=e114]: 首页
      - generic [ref=e115]: /
      - generic [ref=e116]: 全景图谱
    - main [ref=e117]:
      - generic [ref=e118]:
        - generic [ref=e119]:
          - generic [ref=e120]:
            - img [ref=e123]
            - generic [ref=e125]:
              - generic [ref=e126]: 技术领域
              - generic [ref=e127]: "0"
              - generic [ref=e128]: 知识图谱核心分类
          - generic [ref=e129]:
            - img [ref=e132]
            - generic [ref=e135]:
              - generic [ref=e136]: 岗位数
              - generic [ref=e137]: "0"
              - generic [ref=e138]: IT 行业全覆盖
          - generic [ref=e139]:
            - img [ref=e142]
            - generic [ref=e144]:
              - generic [ref=e145]: 技能数
              - generic [ref=e146]: "0"
              - generic [ref=e147]: 持续增长中
          - generic [ref=e148]:
            - img [ref=e151]
            - generic [ref=e154]:
              - generic [ref=e155]: 关系数
              - generic [ref=e156]: "0"
              - generic [ref=e157]: 知识关联网络
          - generic [ref=e158]:
            - button "简历匹配" [ref=e159] [cursor=pointer]:
              - img [ref=e161]
              - generic [ref=e163]: 简历匹配
            - button "JD 抽取" [ref=e164] [cursor=pointer]:
              - img [ref=e166]
              - generic [ref=e168]: JD 抽取
            - button "演化趋势" [ref=e169] [cursor=pointer]:
              - img [ref=e171]
              - generic [ref=e173]: 演化趋势
        - generic [ref=e174]:
          - generic [ref=e175]:
            - navigation [ref=e176]:
              - generic [ref=e177]: 领域概览
            - radiogroup "radio-group" [ref=e178]:
              - generic [ref=e179]:
                - radio "领域" [checked] [ref=e180]
                - generic [ref=e181] [cursor=pointer]: 领域
              - generic [ref=e182]:
                - radio "技术栈" [ref=e183]
                - generic [ref=e184] [cursor=pointer]: 技术栈
              - generic [ref=e185]:
                - radio "级别" [ref=e186]
                - generic [ref=e187] [cursor=pointer]: 级别
          - generic [ref=e188]:
            - generic [ref=e189]:
              - button "2D" [ref=e190] [cursor=pointer]
              - button "3D" [ref=e191] [cursor=pointer]
            - generic [ref=e193]:
              - generic [ref=e194]: 领域
              - generic [ref=e196]: 岗位
              - generic [ref=e198]: 技能
            - button "显示演化" [ref=e200] [cursor=pointer]:
              - generic [ref=e201]: 显示演化
        - generic [ref=e202]:
          - main [ref=e203]:
            - generic [ref=e204]:
              - generic [ref=e207]:
                - img [ref=e209]
                - generic [ref=e211]: 力导向布局计算中...
              - generic [ref=e212]:
                - img [ref=e214]
                - paragraph [ref=e217]: 图谱数据为空
                - paragraph [ref=e218]: 请确认后端服务已启动并有数据接入
              - generic [ref=e219]:
                - button [ref=e220] [cursor=pointer]:
                  - img [ref=e222]
                - button [ref=e224] [cursor=pointer]:
                  - img [ref=e226]
                - button [ref=e228] [cursor=pointer]:
                  - img [ref=e230]
                - button "力" [ref=e234] [cursor=pointer]:
                  - generic [ref=e235]: 力
                - button [ref=e236] [cursor=pointer]:
                  - img [ref=e238]
                - button [ref=e240] [cursor=pointer]:
                  - img [ref=e242]
                - button [ref=e245] [cursor=pointer]:
                  - img [ref=e247]
                - button [ref=e249] [cursor=pointer]:
                  - img [ref=e251]
                - button [ref=e254] [cursor=pointer]:
                  - img [ref=e256]
                - button [ref=e258] [cursor=pointer]:
                  - img [ref=e260]
                - button "🔄" [ref=e263] [cursor=pointer]:
                  - generic [ref=e264]: 🔄
                - generic [ref=e266]: 0 节点
          - complementary [ref=e267]:
            - generic [ref=e269]:
              - img [ref=e271]
              - paragraph [ref=e274]: 点击节点查看详情
        - generic [ref=e276]:
          - img [ref=e278]
          - textbox "搜索岗位、技能、领域..." [ref=e281]
    - contentinfo [ref=e282]:
      - generic [ref=e283]: StarMap · 人才能力星云导航系统
      - generic [ref=e284]: "|"
      - generic [ref=e285]: XH-202621
```

# Test source

```ts
  166 |   tolerance = DEFAULT_TOLERANCE,
  167 | ): boolean {
  168 |   if (apiVal === renderedVal) return true
  169 |   if (typeof apiVal === 'number' && typeof renderedVal === 'number') {
  170 |     if (apiVal === 0 && renderedVal === 0) return true
  171 |     const denom = Math.max(Math.abs(apiVal), Math.abs(renderedVal), 1)
  172 |     return Math.abs(apiVal - renderedVal) / denom <= tolerance
  173 |   }
  174 |   return false
  175 | }
  176 | 
  177 | /**
  178 |  * 逐字段比对 API 响应 vs 渲染数据
  179 |  *
  180 |  * @param apiData 后端返回的原始 JSON
  181 |  * @param renderedData 前端渲染的数据（从 DOM/Pinia 提取）
  182 |  * @param fields 要比对的字段列表，支持嵌套路径 "a.b.c"
  183 |  * @param tolerance 浮点容差
  184 |  */
  185 | export function compareApiVsRendered(
  186 |   apiData: Record<string, unknown>,
  187 |   renderedData: Record<string, unknown>,
  188 |   fields: string[],
  189 |   tolerance = DEFAULT_TOLERANCE,
  190 | ): ComparisonResult[] {
  191 |   return fields.map((field) => {
  192 |     const apiValue = getNestedValue(apiData, field)
  193 |     const renderedValue = getNestedValue(renderedData, field)
  194 |     const match = compareWithTolerance(apiValue, renderedValue, tolerance)
  195 |     return {
  196 |       field,
  197 |       apiValue,
  198 |       renderedValue,
  199 |       match,
  200 |       reason: match ? undefined : `api=${apiValue} vs rendered=${renderedValue}`,
  201 |     }
  202 |   })
  203 | }
  204 | 
  205 | /** 断言所有比对结果匹配 */
  206 | export function assertAllMatch(results: ComparisonResult[]): void {
  207 |   const mismatches = results.filter(r => !r.match)
  208 |   if (mismatches.length > 0) {
  209 |     const details = mismatches
  210 |       .map(r => `${r.field}: ${r.reason}`)
  211 |       .join('\n  ')
  212 |     throw new Error(`Data mismatch:\n  ${details}`)
  213 |   }
  214 | }
  215 | 
  216 | // ── 辅助 ──
  217 | 
  218 | function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  219 |   const keys = path.split('.')
  220 |   let current: unknown = obj
  221 |   for (const key of keys) {
  222 |     if (current === null || current === undefined) return undefined
  223 |     if (Array.isArray(current)) {
  224 |       current = current[parseInt(key, 10)]
  225 |     } else if (typeof current === 'object') {
  226 |       current = (current as Record<string, unknown>)[key]
  227 |     } else {
  228 |       return undefined
  229 |     }
  230 |   }
  231 |   return current
  232 | }
  233 | 
  234 | // ── 页面通用等待 ──
  235 | 
  236 | /** 等待页面加载完成 */
  237 | export async function waitForApp(page: Page, timeout = 10000): Promise<void> {
  238 |   try {
  239 |     await page.waitForLoadState('networkidle', { timeout })
  240 |   } catch {
  241 |     // networkidle 可能超时（SSE 连接），忽略
  242 |   }
  243 |   await page.waitForTimeout(500)
  244 | }
  245 | 
  246 | /** 等待 Element Plus loading 消失 */
  247 | export async function waitForLoadingDone(page: Page, timeout = 15000): Promise<void> {
  248 |   const loading = page.locator('.el-loading-mask, .el-loading-spinner')
  249 |   if (await loading.count() > 0) {
  250 |     await expect(loading.first()).toBeHidden({ timeout })
  251 |   }
  252 | }
  253 | 
  254 | /** 等待 API 调用完成 */
  255 | export async function waitForApiCall(
  256 |   collector: ApiCollector,
  257 |   pattern: string | RegExp,
  258 |   timeout = 10000,
  259 | ): Promise<ApiCall> {
  260 |   const start = Date.now()
  261 |   while (Date.now() - start < timeout) {
  262 |     const call = collector.lastCall(pattern)
  263 |     if (call) return call
  264 |     await new Promise(r => setTimeout(r, 200))
  265 |   }
> 266 |   throw new Error(`API call matching ${pattern} not received within ${timeout}ms`)
      |         ^ Error: API call matching /graph/overview not received within 15000ms
  267 | }
```