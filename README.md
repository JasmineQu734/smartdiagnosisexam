# 三层人才技能培训与考试管理系统

MVP 按项目书顺序落地：主数据与权限、考试、个人系统、管理板块、实操任务、规则引擎和 Agent 接口桩。三个 Agent 桩统一走数据库规则，响应 `source=rule`；个人个性化诊断与公司运行诊断已改成「查事实 → 大模型出结论 → 契约校验 → 不合格回退内置结论」，配好大模型后响应 `source=model`，没配也照旧离线可用。所有建议一律 `need_human_confirm=true`，必须人工确认。

系统只用 MySQL 一套数据库：主数据、业务数据、Agent 结果、审计留痕与后台展示数据集全部落库，不依赖 PostgreSQL / Redis / 对象存储 / 消息队列。

## 目录

```text
backend/                 Spring Boot 3 API（spring-boot-starter-jdbc + JdbcTemplate，无 ORM）
frontend/                Vue 3 + Vite + Element Plus
db/init/                 MySQL 8+ DDL 与种子数据（001 结构 → 002~009 种子 → 010~013 增量脚本，按序执行）
docker-compose.yml       MySQL、API、Web
```

## 启动

```powershell
docker compose up --build
```

- API Swagger：`http://localhost:8080/swagger-ui.html`
- Web：`http://localhost:5173`
- MySQL：`127.0.0.1:3306/train_system`（`root` / `123456`）。容器 MySQL 默认只绑本机回环地址，局域网与其他机器连不到。
- 这些端口被本地开发环境占用时（本地 MySQL、`mvn spring-boot:run`、`npm run dev`），在仓库根目录建 `.env` 改宿主端口：`MYSQL_PORT=3307`、`API_PORT=8081`、`WEB_PORT=5174`。容器内端口不变，容器之间仍走 `mysql:3306` 与 `backend:8080`。
- 数据库密码与 MySQL 绑定网卡同样走 `.env`：`MYSQL_ROOT_PASSWORD`（默认 `123456`）、`MYSQL_BIND`（默认 `127.0.0.1`）。可复制 `.env.example` 作模板；部署时的必改项见下文「部署」。
- 拉取镜像卡住或超时（国内直连 Docker Hub 不通）时，在 Docker Desktop → Settings → Docker Engine 的 `registry-mirrors` 中加镜像加速地址，保存后重启 Docker。

本地开发：后端在 `backend` 执行 `mvn spring-boot:run`，前端在 `frontend` 执行 `npm install; npm run dev`。Java 需要 25+（本机用 JDK 17 时构建加 `-Djava.version=17`），Node 需要 20+。

### 分发包（Docker 版，给别人用的一键启动包）

收件人只需要装 Docker Desktop，不需要 Java / Node / MySQL。

- 打包（维护者）：`.\tools\launcher\make-package.ps1 -Zip` → 产出 `dist\PowerTrain-1.0.0.zip`；加 `-WithImages` 会连三个运行时镜像一起导出（约 2 GB），对方完全离线也能启动，不加则首次启动需联网拉基础镜像并构建。
- 收件人：解压后双击 `启动.bat`。只体检不改动用 `启动.bat -Check`，停止用 `停止.bat`，改了代码重建用 `启动.bat -Rebuild`。
- 脚本做的事：检查 Docker（没跑就拉起 Docker Desktop 等它就绪）→ 没有 `.env` 就生成一份（随机数据库密码 + 随机 `AUTH_SECRET` + 自动避让被占用的端口）→ 拉起容器 → 等网页就绪 → 打印局域网访问地址。
- **`.env` 永远不进包**（里面有数据库密码、令牌签名密钥、大模型 key）：打包脚本主动排除，并在包里出现 `.env` 时直接中止。开箱即用的默认是 `AI_ENABLED=false`，诊断走内置规则引擎，照样出结论。（Windows 免安装版是例外，见下一节：它随包预置一份 `AI_API_KEY` 留空的 `.env`。）
- 局域网地址取自 `route print -4` 里 metric 最小的那条默认路由的 Interface 列，不是 `ipconfig` 的第一条——VMware / Hyper-V / WSL / 手机热点这些虚拟网卡也有 IP，挑错了对方连不上。脚本另外会把其余候选 IP 列出来兜底。
- 别人打不开时的排查顺序：是否同一网段 → 用的是局域网地址而不是 `localhost` → Windows 防火墙是否放行入站 TCP `${WEB_PORT}`（以管理员身份运行脚本会自动加规则，否则屏幕会打印现成的 `netsh` 命令）→ 路由器/热点是否开了终端隔离。
- 对外演示前必知：登录已校验账号口令（SHA-256 散列比对，初始密码见「演示账号」表），但仍无验证码防爆破与登录失败锁定，且账号无真实身份源，只能放在可信内网，不要直接映射公网。

### 分发包（Windows 免安装版，收件人什么都不用装）

收件人拿到文件夹、双击 `start.bat` 就能用：不需要 Docker、Java、Node、MySQL，也不需要联网。

- 打包（维护者）：`.\tools\launcher-native\make-package.ps1 -Zip` → 产出 `dist\PowerTrain-Win-1.0.0.zip`。参数：`-MySqlHome`（绿色版 MySQL 来源目录，默认 `D:\MySQL`）、`-JdkHome`（带 `jmods` 的 JDK，默认取 `JAVA_HOME`）、`-SkipWebBuild`（前端已构建过时跳过 `vite build`）。每次重打先清空 `dist\PowerTrain-Win-<版本>\`，免得上一次演练留下的数据库混进包里。打包时会用包内自己的 `tools/start.ps1 -InitEnv` 预置一份 `.env`：端口按打包机当时的空闲端口写、数据库口令与 `auth.secret` 随机生成、大模型开关打开、`AI_API_KEY` 留空；出包前校验 `AI_API_KEY` 必须为空，模型 key 不会被夹带出去。
- 包内结构：`app\backend.jar`（预构建后端）+ `app\webapp\`（预构建前端静态文件）+ `app\db-init\`（建库脚本）+ `runtime\jre\`（jlink 裁出的精简 JRE，44 MB）+ `runtime\mysql\`（绿色版 MySQL，161 MB）+ `tools\`（启动与停止脚本）。解压后约 258 MB。
- 为什么收件人不需要 Node / Python：前端在打包机上一次 `vite build` 出静态文件，而这个前端是**无路由的单页应用**，直接由后端用 `--spring.web.resources.static-locations` 托管，所以既没有 nginx 也没有 Vite 常驻进程。整套只有 **Java 与 MySQL 两个进程、一个端口**，网页与 `/api/v1` 同源，不需要反向代理。
- 收件人侧行为：检测包内运行时（系统里已有的 Java / MySQL 只报告、不碰）→ `.env` 沿用包内预置的那一份，缺失才重新生成（随机数据库口令 + 随机 `auth.secret` + 自动避让被占用端口）→ `mysqld --initialize-insecure` 建独立数据目录并启动 → 按序跑 `app\db-init` 的建库脚本 → 起后端（`--server.address=0.0.0.0`，局域网可达）→ 等网页就绪 → 开浏览器并打印局域网地址。
- 大模型连通性体检：`.env` 里填了 `AI_API_KEY` 时，启动（以及 `-Check`）会向 `AI_BASE_URL` 发一次最小请求（`max_tokens=16`），把结果直接打在屏幕上：`大模型连通：xxx 有响应` / `大模型连不通：<原因>`（key 不对 401、模型不存在 404、超时、域名解析失败、被防火墙/代理拦住）。没填 key 时提示「大模型已开启，但还没填 key」。探活失败只提示、不拦启动 —— 诊断仍按既有约定回退内置规则结论（`fallback_note`）。之前「填了 key 却像没接上」只能靠翻后端日志，现在一眼可见。
- 建库脚本**不是每次启动都重跑**：`data\db-init.stamp` 记脚本清单指纹，没变就跳过；升级时新增的脚本会自动补跑。首次建完是 53 张表。
- 端口默认 Web `8080` / MySQL `3307`（刻意避开本机常见的 3306），被占用就自动往后挑并写回 `.env`。停止用 `stop.bat`，数据在 `data\` 里。
- 打包前会比对 `jar` 与源码时间戳，`jar` 比源码旧就直接中止，避免把旧代码打进包。
- 改这套脚本时别踩回去的两个坑：① `data\my.ini` 里**不能加** `skip-name-resolve` —— 加了之后 MySQL 不再把 `127.0.0.1` 当成 `localhost`，`'root'@'localhost'` 匹配不上，任何连接都报 `1130 Host is not allowed to connect`；② 建库脚本要用 `Start-Process -RedirectStandardInput` 喂进 mysql 客户端 —— `mysql -e "source x.sql"` 在当前客户端版本上会把 `source` 当 SQL 发给服务器报 `1064`，而 PowerShell 管道在 PS 5.1 下默认按 ASCII 编码，会让中文种子数据变成问号。
- 对外演示前必知：登录已校验账号口令，但仍无防爆破锁定与真实身份源，只能放在可信内网。

### 数据库（只用 MySQL）

连接参数在 `backend/src/main/resources/application.yml`，默认 `jdbc:mysql://localhost:3306/train_system`、`root` / `123456`，可用 `SPRING_DATASOURCE_URL` / `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD` 覆盖。

建库按顺序执行 `db/init` 下的十一个脚本（001 建库建表 → 002 规则与内容种子：气体规则 / 报告模板框格 / 归因关键词 / 知识点 / 练习题 → 003 主数据与数据集：账号角色 / 技能课程 / 考试 / 展示数据集 → 004 口径细化 → 005 标准依据 → 006 外网课程搜索的来源平台与课程库 → 007 组长资料导入台账：`material_doc` 原件留档 / `material_item` 候选题台账 → 008 规则引擎：`rule` 补公共字段与匹配开关 / `rule_result` 执行留痕 / 6 条规则种子改成声明式条件 → 009 气体检测归因：`rule` 补匹配分组与组内命中上限 / 场景 `REPORT_GAS` 的 12 条归因规则（原先写在 Java 里的判定搬进表） → 010 报告 SOP 填报字段：给 `task_report` 补 `sop_status`（空 = 未填报 / FOLLOWED / DEVIATED / NOT_APPLICABLE）与 `sop_deviation`（偏差说明），让归因能区分「技能不够」与「没按规程做」 → 011 公司运行诊断兜底口径：把原先写在 `CompanyController` 里的总述与同步板块文案搬进 `dataset_meta`，顺序不可调换） → 012 规则校准：考试阈值与等级差距规则按评测结论校准 → 013 登录口令初始化：给全部账号写入初始口令散列（SHA-256(username + ':' + password)，初始密码 = `123456`））：

```powershell
$env:MYSQL_PWD = '123456'
cmd /c "mysql -uroot --default-character-set=utf8mb4 < db\init\001_schema.sql"
foreach ($f in '002_seed.sql','003_seed_datasets.sql','004_seed_refine.sql','005_standard_ref.sql','006_external_course.sql','007_material_import.sql','008_rule_engine.sql','009_report_gas_rules.sql','010_report_sop_field.sql','011_exec_diagnosis_baseline.sql') {
  cmd /c "mysql -uroot --default-character-set=utf8mb4 < db\init\$f"
}
```

`005_standard_ref.sql` 由 `tools/fetch-standards.mjs` 抓取国家标准全文公开系统后生成，可重复执行刷新标准依据库。
`006_external_course.sql` 由 `tools/fetch-courses.mjs` 生成（同时核验各平台检索地址的 HTTP 状态并写入 `http_code` / `checked_at`），可重复执行刷新外网课程搜索的平台与课程库。`007_material_import.sql` 为组长导入文档 / SOP 填报补齐两张台账表（`material_doc` 记录原件留档与正文摘录，`material_item` 记录 Agent 识别出的每条候选题及其审核状态与入库题号），并刷新 SOP 模板与「导入文档」入口的库内口径；全部为 `CREATE TABLE IF NOT EXISTS` / `ON DUPLICATE KEY UPDATE`，对已有库直接补跑即可。`008_rule_engine.sql` 是规则引擎的补列 + `rule_result` 建表 + 规则种子规范化（补列前先查 `information_schema`，MySQL 8 没有 `ADD COLUMN IF NOT EXISTS`；重跑只覆盖规则定义，不动 `enabled` / `status`，不会把管理员手工停用的规则又打开）。`009_report_gas_rules.sql` 给 `rule` 表补 `rule_group`（匹配分组）与 `max_hits`（组内命中上限）两列，并把气体检测归因的判定从 `ReportAnalysisService` 的硬编码搬进 `rule` 表（场景 `REPORT_GAS`，12 条：定档 5 条 + 关键词 7 条），同 008 一样可重复执行、不重开手工停用的规则。`010_report_sop_field.sql` 给 `task_report` 补 `sop_status` / `sop_deviation` 两列并在报告模板里新增「SOP 执行情况」一节：报告归因要区分「技能不够」与「没按规程做」，这两件事在现象描述里都是自然语言、规则判不了，得让组长填报时给出一个可枚举的答案；字段缺失只判为「未知」，绝不默认成「未按 SOP」，否则缺数据会自动变成「人为问题」的结论。`011_exec_diagnosis_baseline.sql` 给 `dataset_meta` 的 `exec.diagnosis` 行补 `summary`（总述段落）与 `updated_modules`（本次同步板块）：这两段文案原先写死在 `CompanyController` 里，改成「大模型出结论、不合格回退内置结论」后兜底路径直接下发库里的 payload，文案必须入库，管理员改库即改兜底结论。两段脚本都是补列 / 补口径，不覆盖其他内容，可直接对已有库补跑。`010` 还会把仓库自带的那 4 份演示报告的 SOP 执行情况按报告正文本身补上（只有 `RPT-20260919-0003` 的正文写明「先行进入的作业人员出现头晕、胸闷不适」，据实记为未按 SOP，其余 3 份记为已按 SOP），并且只在字段为空时补：这样已有数据卷与空卷跑出来的演示数据才一致。 `012_rule_calibration.sql` 做规则集校准：把 `EXAM_LOW_SCORE` 的 `score < 60` 与 `SKILL_GAP_L3` 的 `required_level = 3` 两处字面量改成引用事实（`EXAM_BELOW_PASS`、`SKILL_BELOW_REQUIRED`，比较 `pass_score` 与 `required_level`），补 `SAFETY` 分组的两条安全规则（授权类违规一票否决、扣分记录判中），并给 `REPORT_GAS_WITHIN_NEAR` 补下界 `ratio > -0.10`，使余量充足时终端规则可达。被取代的两条保留定义但置 `enabled = 0`，供历史结论回溯。规则总数 22 条，其中 20 条参与求值。

### 部署

用 compose 自带的 MySQL 容器，不要挂宿主机已装的 MySQL：库版本、账号、建库建表与种子数据都由 `db/init` 在数据卷首次初始化时自动完成，换台机器只要 `docker compose up --build` 就能复现同一套环境。

- 必改项：把 `MYSQL_ROOT_PASSWORD` 换成强密码（写进 `.env` 或用环境变量注入），不要把 `123456` 带到服务器；`MYSQL_BIND` 保持 `127.0.0.1`，容器 MySQL 不需要对宿主机网段开放。
- 只对外暴露 Web 端口：`frontend` 发布 `${WEB_PORT}`，`backend` 的 `${API_PORT}` 固定绑在 `127.0.0.1`（不绑 `0.0.0.0`，避免绕过 nginx 把 API 开到宿主机所有网卡），容器 MySQL 绑 `MYSQL_BIND`。前端用相对路径 `/api/v1` 调接口（`frontend/src/api.js`），由 nginx 反代到 `backend:8080`（`frontend/nginx.conf`），换域名或换 IP 都不用改前端；正式发布时在更外层再加 HTTPS（Nginx / Caddy / 云负载均衡）。本机要看 Swagger 或直连 API 走 `http://127.0.0.1:${API_PORT}/swagger-ui.html`，不需要给局域网开 API 端口。
- 三个服务都带 `restart: unless-stopped`：宿主机重启后自动拉起；`docker compose stop` 手工停掉的不再自动起。
- 后端与前端的镜像名在 `docker-compose.yml` 里写死为 `powertrain/backend:1.0.0` / `powertrain/frontend:1.0.0`（`image:` 与 `build:` 并存，构建产物就打这个 tag）。不写死的话镜像名会随文件夹名/Compose 项目名变化，改个文件夹名 compose 就当新镜像重新构建——离线分发包正是靠这个固定 tag 才能 `docker load` 后直接用。换版本时改这两行即可（不涉及接口路径、DTO 或表名）。
- 组长上传的资料原件与生成的报告文档放在具名卷 `trainfiles`（容器内 `/var/lib/power-train`），与数据库分开，重建容器不丢；`docker compose down` 不加 `-v` 即保留。备份时记得连这个卷一起备。
- 改密码对已存在的数据卷不生效：`MYSQL_ROOT_PASSWORD` 只在数据卷首次初始化时写入。老库换密码需进容器执行 `ALTER USER`，或 `docker compose down -v` 重建（会清空数据）。
- 升级重建：`docker compose up --build`；停止服务用 `docker compose down`，不要加 `-v`，`-v` 会连同 `mysqldata` 数据卷一起删除。
- 备份（密码取自容器内的 `MYSQL_ROOT_PASSWORD`，无需交互输入）：`docker compose exec -T mysql sh -c 'mysqldump -uroot -p$MYSQL_ROOT_PASSWORD train_system' > backup.sql`
- 换成独立 MySQL 或云数据库 RDS：把 `SPRING_DATASOURCE_URL` 指过去（`backend/src/main/resources/application.yml` 读的就是这个环境变量），再删掉 compose 里的 `mysql` 服务即可，代码不用改。

### 部署自检

交付或上线前用空卷跑一遍初始化，验证 `db/init` 十一个脚本能一次到位，且不影响正在使用的数据卷：

```powershell
docker run -d --name init-check -e MYSQL_ROOT_PASSWORD=123456 -e MYSQL_DATABASE=train_system -v "${PWD}/db/init:/docker-entrypoint-initdb.d:ro" mysql:8.4
docker exec init-check mysqladmin ping -h 127.0.0.1 -uroot -p123456
docker exec init-check mysql -uroot -p123456 -D train_system -N -e "select count(*) from information_schema.tables where table_schema = database()"
docker logs init-check 2>&1 | Select-String ERROR
docker rm -f -v init-check
```

期望结果：表数与 `db/init` 里定义的一致（当前 53 张），`docker logs` 无 ERROR；`ping` 能通就代表十一个脚本已执行完（初始化阶段 mysqld 不监听 TCP，能连上说明临时实例已结束、正式实例已启动）。

若现用数据卷是旧版本初始化的（表数少于脚本定义，典型是缺 `external_course` / `external_course_source` / `material_doc` / `material_item` / `rule_result` 这些后期新增表，以及 `task_report` 缺 `sop_status` / `sop_deviation` 两列（010）、`dataset_meta` 的 `exec.diagnosis` 缺兜底总述文案（011）），**不必删卷重建**：按「数据库（只用 MySQL）」一节的顺序，把缺的脚本对容器库补跑一遍即可（这些脚本均为 `CREATE TABLE IF NOT EXISTS`，可重复执行）：

```powershell
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\006_external_course.sql"
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\007_material_import.sql"
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\008_rule_engine.sql"
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\009_report_gas_rules.sql"
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\010_report_sop_field.sql"
cmd /c "docker compose exec -T mysql mysql -uroot -p123456 --default-character-set=utf8mb4 train_system < db\init\011_exec_diagnosis_baseline.sql"
```

## 演示账号与角色权限

| 账号 | 初始密码 | 角色 | 页面范围 | 可见内容 |
|---|---|---|---|---|
| zhangwei | 123456 | EMPLOYEE | PERSONAL（本人） | 技能雷达 / 个人自画像 / 个人能力 / 记忆展示 / 成长轨迹 / 差距与建议 / 学习与考试 / 实操任务，全部只返回本人数据 |
| limin | 123456 | TEAM_LEAD | PERSONAL（本人 + 班组） | 员工全部板块 + 班组报告（每次实操活动上传报告，作为运行诊断 Agent 的输入之一） |
| wangzong | 123456 | EXECUTIVE | COMPANY（全公司） | 公司总览 / 运行诊断 Agent，看全体员工汇总数据，没有个人画像页面 |
| admin | 123456 | ADMIN | PLATFORM（平台） | 数据与运维 / 审计日志：员工档案、考试配置、试卷发放、审计，既看不到个人画像也看不到老总页面 |

初始密码统一为 `123456`（含未在表中列出的 `wangjianguo` / `sunqian`，由 `db/init/013_login_password.sql` 写入散列；`sunqian` 状态为 PENDING，登录返回 403）。修改口令即更新 `app_user.password_hash`（口径：`SHA-256(username + ':' + password)` 十六进制）。

员工登录后只能看到自己的完整能力画像、记忆展示与学习建议；组长本身也是员工，板块全上再多一个班组报告；老总看全公司总数据与运行诊断；系统管理员只看平台数据，不做业务决策。

### 四种身份的视觉识别

四个演示身份共用同一套设计系统，只换识别色、视图徽标与头像形态，进系统后一眼能分清「现在是谁在看」。规则集中在 `frontend/src/App.vue` 的 `ROLE_THEME` 与 `frontend/src/roles.css`：

| 身份 | 识别色 | 侧边栏徽标 | 头像形态 | 顶栏铭牌 |
|---|---|---|---|---|
| 张伟 `zhangwei` | 工业青 `#12909a` | 员工视图 · 仅本人数据 | 圆角方 | 员工 · 变电运维一班 |
| 李民 `limin` | 班组琥珀 `#c2740c` | 组长视图 · 本人 + 班组数据 | 圆形 + 同色光圈 | 组长 · 变电运维一班 |
| 王总 `wangzong` | 决策紫 `#5a49b8` | 老总视图 · 全公司数据 | 圆形 + 金色描边 | 公司上级（老总） · 中心管理层 |
| 系统管理员 `admin` | 平台石墨 `#43607c` | 管理员视图 · 平台数据 | 方形 | 系统管理员 · 信息中心 |

五处同时生效：页面左上角的问候语（`Hello，欢迎回来，<身份名>`，身份名用识别色加粗，右侧保留 `2026 · 变电运维中心`）、侧边栏身份徽标与导航选中色、顶栏身份铭牌、页面标题下的角色说明条、登录页（整张卡与「进入系统」按钮跟随所选身份换色，每个身份行自带自己的配色）。切换身份时五处的颜色、徽标与数据范围说明会一起变，避免四个身份看起来像同一个页面。

后端按路径前缀统一鉴权（`rbac/RoleInterceptor`），越权返回 **HTTP 403 + `code=40301`**，响应 `data` 内含 `role` 与 `scope`：

| 路径前缀 | 允许角色 |
|---|---|
| `/api/v1/personal/**` | `EMPLOYEE`、`TEAM_LEAD` |
| `/api/v1/team/**` | `TEAM_LEAD` |
| `/api/v1/tasks/**` | `TEAM_LEAD`（检测报告只有组长填报，普通员工只查看报告，越权 `403 / 40301`） |
| `/api/v1/management/**`、`/api/v1/exec/**` | `EXECUTIVE` |
| `/api/v1/admin/**` | `ADMIN` |

旧角色 `DEPARTMENT_MANAGER` 归一化为 `TEAM_LEAD`，未识别角色一律按 `EMPLOYEE` 处理。登录成功后后端签发令牌（`POST /auth/login` 返回 `data.token`），前端把它放进 `Authorization: Bearer` 头，后端 `rbac/AuthFilter` 校验令牌后再交给 `rbac/RoleInterceptor` 按路径前缀授权；请求头里的 `X-User` / `X-Role` 不再被采信，改请求头伪造身份已无效。导航项与登录落点由 `NAV_BY_ROLE` / `LANDING_BY_ROLE` 决定。

登录为账号 + 口令（`SHA-256(username + ':' + password)` 散列比对，见 `db/init/013_login_password.sql`），接口返回服务端 HMAC 签名的令牌（`AUTH_SECRET` 作密钥，默认 12 小时有效，账号不存在或密码错误统一 `401`）；生产环境仍需接入内网统一身份（或 Spring Security + 刷新令牌）、加盐慢散列与真实身份源。

### 员工六大板块

| 板块 | 接口 | 内容 |
|---|---|---|
| 技能雷达 | `GET /personal/skill-radar` | 当前等级 vs 岗位要求 vs 公司未来需求，含 `level_label` / `state` / `priority` / `note` |
| 个人自画像 | `GET /personal/self-portrait` | 基本信息 / 职业目标 / 发展意愿 / 自我评价 / 师傅评价 / 协作评价 / 岗位匹配度 |
| 个人能力 | `GET /personal/abilities` | 硬技能 / 软技能 / 安全能力 / 实操能力 / 考试能力 / 证书能力 |
| 记忆展示 | `GET /personal/memories` | 学习 / 错误 / 实操 / 考试 / 安全 / 带教 / 复盘七类记忆，按时间线 |
| 成长轨迹 | `GET /personal/growth` | 技能等级、证书、考试、任务、培训、安全记录与晋升准备度 |
| 差距与建议 | `GET /personal/advice`、`POST /personal/agent-diagnose` | 差距汇总基线 + 个性化 Agent 实时诊断（结论、差距、学习路径、复合型人才路线），结果回写记忆库并同步各板块；`source` 为 `rule`（内置结论兜底）或 `model`（大模型依据库内事实出结论，不合输出契约即自动回退并在 `fallback_note` 写明原因） |
| 学习与考试 | `GET /personal/resources`、`GET /personal/course-search` | 推荐资源窗口：12 条资料，站内跳转对应板块，外网 10 条新窗口打开公开资料站；窗口顶部是外网课程搜索（关键词 / 平台 / 技能 / 等级），命中外网课程库并给出各公开平台的实时检索直达链接 |
| 练习题 | `GET /personal/practice/overview`、`POST /personal/practice/draw`、`POST /personal/practice/submit` | 题库 21 题起步（继电保护 / 倒闸操作 / 高压试验 / 故障录波 / 安全规程），Agent 按“缺口权重 × 历史正确率”抽题；作答与解析都在同一个弹窗内完成，点「交卷」直接出分数与逐题解析（不再有“交卷并解析”两步），答错写入记忆库 |
| 考试中心 | `GET /personal/exams`、`POST /exams/{examId}/start`、`POST /exams/{examId}/submit` | 只有管理员统一开考后按钮才可点「进入考试」（页面顶部同时给出开考横幅，可直接进入开考中的场次）；管理员未开考时按钮为灰色的「等待管理员开考」，页面提示等管理员在「考试配置 → 考试清单」点「开始考试」，接口也拒绝发卷。进入后是整屏作答页：顶部答题卡标注每题作答状态并可跳题、显示剩余时间（到点自动交卷），手动交卷若有漏答会先确认，交卷即出分数、逐题解析与出处，并写入考试记忆 |

以上接口只返回当前身份本人数据，员工之间互不可见。

外网课程搜索（学习与考试 → 推荐资源窗口顶部）：`GET /personal/course-search?q=&platform=&skill=&level=`，按关键词在 `external_course` 的外网课程库里打分检索（标题 6 分 → 检索词 4 分 → 标签 / 技能 3 分 → 平台栏目 2 分 → 匹配理由 1 分，逐条返回 `match_hits` 命中说明），同时返回 `internal`（站内命中的推荐资源与课程库课程，带 `jump` 可跳板块）、`platforms`（把 `external_course_source.search_url` 里的 `{kw}` 换成关键词后的实时检索地址，前端一律新窗口打开）、`hot_keywords`（按本人技能缺口排序的检索词）与 `gap_skills`；关键词为空时按当前技能缺口（`employee_skill` 中 `level < required_level`，缺得越多越靠前）排序，并列的缺口课程带 `gap_match` 标记。外网课程库只收录各平台公开的检索入口与检索关键词，不复制平台课程正文；平台与课程由 `tools/fetch-courses.mjs` 生成 `db/init/006_external_course.sql`（含每个平台检索地址的真实 HTTP 核验状态码），导入后落在 `external_course_source` / `external_course` 两张表。

### 组长 / 老总 / 管理员

- 组长：`GET /team/overview`（班组人员、技能达标与缺报清单）、`GET /team/reports`（实操报告台账：历史台账 + `task_report` 实时报告，同一报告编号只出现一行，报告不在库中则不给文档地址）。
- 组长上传练习资料（两条路径都是「先审核、后入库」）：`GET /team/materials/template` 与 `POST /team/materials/upload`（导入文档：multipart 上传 PDF / docx / txt / md / csv / xlsx / pptx，Agent 读原件正文识别题干 + 选项 + 答案 + 解析并标出处，或按入库目标整理知识章节）、`GET /team/materials`（本班组导入台账与审核进度）、`GET /team/materials/{code}`（批次详情：原件信息、正文摘录、候选题逐条状态与入库题号）；`GET /team/sop/template` 与 `POST /team/sop/generate`（SOP 模板填报 → 候选题）。两条路径都只生成「待审核」候选题，管理员审核通过后才写入题库 / 课程库，员工刷题才抽得到。
- 老总（人才驾驶舱）：`GET /exec/company-overview`（关键指标 6 项：在岗人数/班组、技能达标率、证书有效率、培训完成率、安全风险班组、离职风险人数，含用人成本、人才缺口、班组概览、报告信号与人才风险）、`GET /exec/skill-matrix`（全公司技能矩阵：等级分布、技能达标矩阵、班组维度、关键岗位备份、单点依赖岗位数、强项/待提升名单）、`GET /exec/training-board`（培训看板：完成率、成本结构、培训效果、ROI 测算、部门对比、个人学习计划执行）、`GET /exec/diagnosis`（运行诊断 Agent 输入口径基线）、`POST /exec/agent-diagnose`（点「点击运行诊断 Agent」实时出报告：诊断编号 `EXE-DIA-yyyyMMdd-序号`、生成时间、结论、证据链、问题清单、降本测算与建议措施，结论 `need_human_confirm=true`）、`GET /exec/agent-diagnose/latest`（读回最近一次诊断结论）；`source` 为 `rule`（内置结论兜底）或 `model`（大模型依据库内事实出结论，不合输出契约即自动回退并在 `fallback_note` 写明原因）。
- 管理员（系统管理员后台）用户与权限：`GET /admin/overview`、`/admin/employees`、`/admin/iam`（用户 + 角色）、`/admin/orgs`、`/admin/positions`、`/admin/permissions`。
- 管理员技能与课程：`GET /admin/skills`、`/admin/position-skills`（岗位/技能/等级为平台内部刻度，技术依据逐条引用真实国家标准）、`GET /admin/standards`（标准依据库：来自国家市场监督管理总局「国家标准全文公开系统」的真实标准号 / 名称 / 状态 / 发布-实施日期 / 官网详情页链接，数据由 `tools/fetch-standards.mjs` 抓取并生成 `db/init/005_standard_ref.sql`，导入后落在 MySQL 的 `standard_ref` 表）、`/admin/courses`、`/admin/course-skill-links`、`/admin/question-banks`。
- 管理员资料上传与审核：`GET /admin/course-materials`、`POST /admin/course-materials`（规定格式 `技能编码_名称_等级_版本.pdf`，校验失败返回 `code=40001` 与 `data.field_errors`；通过后由课程 Agent 识别条目，状态为待审核）、`GET /admin/course-materials/{code}`（点开待审核：返回原件信息、原件摘录与 Agent 检索出的题目（题干 / 选项 / 答案 / 解析）或知识章节，Agent 只检索整理、不入库）、`POST /admin/course-materials/review`（管理员核对后才能 approve 写入课程库或累加题库题量，reject 不入库；组长导入 / SOP 填报的批次带逐条台账，可只传勾选的 `approve_ids` 部分通过，未勾选的继续留在待审核）、`POST /admin/courses/review`（待审核课程直接上线或驳回）。
- 管理员考试配置与统一开考：`GET /admin/exam-config`（组卷规则 / 防作弊规则 / 评分规则 / 及格线）、`GET /admin/exams`（含 `available_questions` 题库可抽 / `entered` 已进入 / `submitted` 已交卷）、`POST /admin/exams/start`（统一开考：置为「进行中」，员工端随即出现可点的「进入考试」；未启用考试返回 `started=false`）、`POST /admin/exams/close`（结束本场：置为「已结束」并清空本轮作答记录，员工端收起考试入口；再次开考即开启新一轮并重新发卷）、`GET /admin/papers`、`POST /admin/papers/issue`（按批次发放试卷）。考试清单与员工端共用同一份 `ExamCenter` 状态，题库不足时按实际题量发卷并在清单里显示可抽题量。
- 管理员审计与审核：`GET /admin/audit?category&keyword&from&to`（登录 / 修改 / 审批 / 决策 / 执行 / 回滚分类统计与条件搜索）、`POST /admin/audit/clear`（需 `confirm=true`，清空历史留痕并保留 1 条清除记录）。

## 实操检测报告（框格填报 → 文档生成 → AI 归因）

流程：前端按报告模板框格填报 → 后端校验（必填 + 文本格式）→ 按框格渲染 PDF/Word → 读取文档正文做异常归因 → 结论回到报告等待人工确认。

- 模板框格：`GET /api/v1/tasks/{taskId}/report-template`，每格含必填标记、填写示例与格式要求，前端表单与文档框格共用同一份定义。
- 填报提交：`POST /api/v1/tasks/{taskId}/submit-report`，校验失败返回 `code=40001` 与 `data.field_errors`；成功后返回报告编号、判定结论、归因结果与文档地址。
- 文档下载：`GET /api/v1/reports/{reportId}/document?format=pdf|docx`。PDF 用 PDFBox 内嵌中文字体，Word 用 POI XWPF，两者由同一套框格模型渲染；报告不存在时返回 `404` 与 `code=40004`。
- 归因分析：`POST /api/v1/reports/{reportId}/analyze` 可重新分析。默认使用内置规则引擎（气体阈值 + 现象关键词 + 严重度升级），配置大模型后自动切换到 AI 并保留规则兜底。
- 所有归因结论均为 `need_human_confirm=true`，需班组长确认后闭环。

AI 接口配置（不配置则离线走规则引擎；报告归因、个人个性化诊断、公司运行诊断共用同一份配置，任何一处失败都各自回退自己的内置结论，不影响其他板块）：

本机开发同样读仓库根目录的 `.env`：`application.yml` 里 `spring.config.import` 指向 `./.env` 与 `../.env`，所以 IDE、`mvn spring-boot:run`、`java -jar` 都会自动加载，不必手工导环境变量；容器部署读的也是同一个文件，本机与容器只有一个配置来源。

Windows 免安装版的收件人不用自己建 `.env`：包里已经预置一份（大模型开关打开、`AI_API_KEY` 留空），把 key 填进去、重新双击 `start.bat` 即可；启动窗口会打印一次连通性体检结果，`start.bat -Check` 也会体检（不建库、不起服务）。

配了 key 却像没接上，先查 `AI_TIMEOUT_SECONDS`：思维链模型单次诊断实测个人 35~42 秒、公司 58 秒，默认 20 秒会读超时并静默回退成规则结论（接口带 `fallback_note`，前端不报错，所以很容易被当成「模型没接」）。

下面五个变量也可以直接用环境变量覆盖，优先级高于 `.env`：

```powershell
$env:AI_ENABLED='true'
$env:AI_BASE_URL='https://api.openai.com/v1'   # 兼容 OpenAI /chat/completions
$env:AI_MODEL='gpt-4o-mini'
$env:AI_API_KEY='sk-...'
$env:AI_TIMEOUT_SECONDS='120'
```

容器部署不用手工设环境变量：这五个变量已在 `docker-compose.yml` 的 `backend` 服务透传，值写进 `.env`（已 gitignore）即可，改完 `docker compose up -d --build backend` 生效（配置在启动时读一次）。后端按 `AI_BASE_URL` 自动认两种协议：地址是 Anthropic 形状（`…/apps/anthropic`、`api.anthropic.com`）走 `POST {AI_BASE_URL}/v1/messages`（`x-api-key` + `anthropic-version`），其余按 OpenAI 兼容走 `POST {AI_BASE_URL}/chat/completions`，后者要求模型支持 `response_format={"type":"json_object"}`（Azure OpenAI 的鉴权头与 URL 形状不同，接不了）。思维链模型（deepseek-v4.1-flash / glm / qwen3.8-max 这类）先输出思考再出正文，`AI_TIMEOUT_SECONDS` 建议给到 120（默认 20 会读超时），单次诊断实测个人 34 秒、公司 58 秒；这类模型的思考也占 Anthropic 的 `max_tokens`，代码里已按 16000 预留。API key 没填或填错时不报错，接口会带着 `fallback_note`（含网关的状态码与错误正文）回退内置结论，前端不受影响。

### 接自训练模型（本机 LLaMA-Factory：基座 + LoRA）

诊断结论的来源可以是云端 API，也可以是本机自己微调的模型。本机这套走的是后者：`Qwen2.5-3B-Instruct` + `saves\Qwen2.5-3B-Instruct\lora\sft16_3b` 里的 LoRA 适配器，4-bit 量化、3.09B 参数，跑在 `127.0.0.1:8000`（推理显存约 2.3GB）。

> 为什么不是 7B：本机显卡是 RTX 5060 Laptop（8GB）。诊断样本必须 4096 上下文（答案从第 ~2370 个 token 才开始，`cutoff_len` 低于 2560 时 500 条样本的答案会被整段切掉，这正是早期版本"结论很傻"的原因），而 7B 在 4096 上下文下的训练峰值约 9.5GB，超出 8GB 可用上限，会溢出到共享显存、每步耗时 1 小时。3B 在 4096 上下文下训练峰值约 6GB，本机可完整训练；训练与接入的实测记录见 `docs/` 之外的桌面报告。

要点是**必须用 `api` 模式，不能用 `webui`**：`llamafactory-cli webui` 只提供网页界面（7860），没有任何 HTTP 接口，后端按 `AI_BASE_URL` 调不到它；`llamafactory-cli api` 才提供 OpenAI 兼容的 `/v1/chat/completions`。

1. 双击根目录 **`启动Agent.bat`**（等价于 `powershell -ExecutionPolicy Bypass -File tools\agent\start-agent.ps1`）：脚本先检查 conda 环境、基座模型、LoRA 适配器、端口占用与显存冲突，再启动 api 服务，加载约 20~40 秒。看到 `Uvicorn running on http://0.0.0.0:8000` 就能用了；**那个窗口就是 agent 本体，关掉即停止**（也可以用 `停止Agent.bat`）。要换模型改 `tools\agent\start-agent.ps1` 顶部的 `Adapter` 一行（`saves\Qwen2.5-3B-Instruct\lora\` 下带 `adapter_model.safetensors` 的目录才可用，当前是 `sft16_3b`），换端口用 `-Port`。
2. `.env` 指向它：`AI_BASE_URL=http://host.docker.internal:8000/v1`（后端跑在容器里时；本机直接 `java -jar` 才用 `127.0.0.1`）、`AI_MODEL=qwen2.5-3b-lora`（LLaMA-Factory 不校验这个名字，非空即可，只用于日志与界面标注）、`AI_API_KEY` 填任意非空串（api 模式未开鉴权，但**留空会被判成「未配置大模型」而直接回退规则结论**）、`AI_TIMEOUT_SECONDS=300`。
3. 重启后端进程后，员工端「差距与建议 → 运行个性化 Agent 诊断」的出处会显示 `大模型 qwen2.5-3b-lora · 实时计算`；agent 没启动时自动回退内置规则结论、标注 `规则引擎 v1` 并把原因写进 `fallback_note`，页面不报错。

实测口径（本机 RTX 5060 Laptop 8G）：

- 单次个性化诊断实测约 80 秒，`AI_TIMEOUT_SECONDS` 必须给足（默认 20 秒必定读超时并静默回退）。
- 8G 显存装不下两份模型：`webui` 与 `api` 不能同时开，`启动Agent.bat` 会检查 7860 并直接拦下来；训练时同样要先停掉 `api`（3B 推理占 2.3GB，会让训练溢出换页）。
- LLaMA-Factory 会忽略请求里的 `response_format`，JSON 形状靠「系统提示词 + 解析容错（首个配平 `{}` 提取 + 形状不合格重试一次）+ `DiagnosisContract` 硬校验 + 不合格回退内置结论」保证，所以本机模型与云端模型走的是同一条输出契约（`docs/diagnosis_schema.json`）。
- 容器部署时 `AI_BASE_URL` 要写 `http://host.docker.internal:8000/v1`（容器里的 `127.0.0.1` 不是宿主机），改完 `docker compose up -d --build backend`。

字体解析：`report.font-title` / `report.font-body` 默认 `auto`，顺序为「显式配置（绝对路径或 `classpath:` 资源）→ jar 内 `classpath:fonts/*` → 本机 Windows 字体（simhei / simkai / msyh）→ 容器与服务器字体目录（wqy-zenhei.ttc、DroidSansFallbackFull.ttf 等）」。
Docker 运行镜像已安装 `fonts-wqy-zenhei` + `fonts-droid-fallback`，容器内实际命中 `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`；本机开发命中 `C:/Windows/Fonts/simhei.ttf` 与 `simkai.ttf`。
字体选择注意：PDF 正文的 ToUnicode 必须干净，`Deng.ttf` 会把部分汉字映射成康熙部首（复制 PDF 文本得到“⽓体”），已排除；可用 `REPORT_FONT_TITLE` / `REPORT_FONT_BODY` 强制指定。

## 关键约束

- 前端只调用业务 API 和 `/api/v1/agent/*`，规则接口仅管理员测试使用。
- 员工只能访问本人数据、只能查看检测报告（填报只由组长做，报告填报人恒为班组长）；组长多一份班组报告，并可通过「导入文档」或「SOP 填报」生成候选题，经管理员审核后才入题库；老总才能访问成本、人才缺口、招聘与内部转岗、继任者培养建议；系统管理员只做平台数据与审计。
- 心理/关怀数据默认本人可见，授权心理专员可见，管理端只返回脱敏聚合。
- 安全不合格在人才决策中拥有最高优先级并触发一票否决。
- Agent Controller、DTO、接口路径保持稳定，未来只替换 Service 实现。

完整接口、页面、规则、种子数据见 `docs/api-catalog.md`。
