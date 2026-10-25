════════════════════════════════════════════════════
GLTF 高清模型使用说明（3D 数字孪生园区）
════════════════════════════════════════════════════

〇、已内置的模型（打开页面自动加载）
────────────────────────────────────────
  transformer.glb   25MB  两台主变（GitHub: EngineersTools/TransformerModel，
                           CC 授权，bpy 由 .blend 转出，封闭油箱+储油柜+片式散热器+瓷套管）
  switchgear.glb    16MB  10kV 配电房（GitHub: vittorezhang/threeJs-demo，授权见原仓库）
  stationtrans.glb   2MB  箱式站用变外壳（GitHub: oalles/test-models，CC-BY-SA-4.0，
                           基于 Sketchfab "Electric Distribution Box" by Avadhoot）
  ⚠ 学术/竞赛演示请注明上述出处。
  「高清模型」按钮可重新加载；「导入GLB」可替换/补充本地文件。

一、两种加载方式
────────────────────────────────────────
1. 自动：models/ 目录下的 .glb 会在打开页面时自动加载。
   ⚠ 需要 http 服务（如 `python -m http.server` 或 VS Code Live Server）。
   直接双击 html（file:// 协议）时浏览器会拦截本地文件请求。
2. 手动：「导入GLB」按钮选择本地 .glb 文件。
   ✔ file:// 直接打开也能用（走 FileReader/Blob，无跨域限制）。
   ✔ 文件名决定替换哪台设备（见下表）。

二、文件命名（补充更多设备时使用，必须完全一致，不区分大小写）
────────────────────────────────────────
  transformer.glb      → 同时替换 1号、2号主变（已内置）
  breaker.glb          → 110kV 断路器
  disconnector.glb     → 110kV 隔离开关
  earthing.glb         → 110kV 接地刀闸
  ct.glb               → 110kV 电流互感器
  pt.glb               → 110kV 母线电压互感器
  arrester.glb         → 110kV 避雷器
  switchgear.glb       → 10kV 开关柜室（已内置）
  stationtrans.glb     → 站用变压器（已内置）
  control_room.glb     → 主控保护室

三、模型要求（重要）
────────────────────────────────────────
· 格式：.glb（推荐）或 .gltf（需带 bin + 贴图）
· 单位：米；朝向：Y 轴向上，正面朝 +Z
· 原点：模型底面中心（Blender 导出前 Ctrl+A 全部变换归零）
· 压缩：【不要】勾选 Draco 压缩（当前 loader 未配解码器）
· 材质：PBR（金属度/粗糙度）贴图即可，系统会自动打光
· 缩放：不用精确——加载时会按程序化设备的高度自动等比缩放、
  底面对齐、水平居中，替换后点击巡检/操作功能不受影响

四、免费模型来源（Sketchfab 检索关键词）
────────────────────────────────────────
  · substation transformer  /  power transformer
  · circuit breaker  /  disconnector  /  insulator
  · electrical substation（整站模型可拆件使用）
  下载时选 Downloadable → glTF 格式 → 转存为上表文件名。
  注意遵守模型作者的 CC 授权协议（竞赛演示需标注出处）。

五、Blender 自建导出参数
────────────────────────────────────────
  File → Export → glTF 2.0
  · Format: glTF Binary (.glb)
  · +Y Up 勾选（默认）
  · Compression: 不勾 Draco
  · Transform: Apply Modifiers 勾选
