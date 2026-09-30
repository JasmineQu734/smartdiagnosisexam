SET NAMES utf8mb4;
-- 由 tools/fetch-standards.mjs 抓取生成，写入 MySQL 的 standard_ref / standard_source 表。
-- 平台「标准依据库」的数据源：重新抓取后覆盖执行本文件即可刷新（幂等）。
USE train_system;

INSERT INTO `standard_source` (`id`, `source`, `source_url`, `fetched_at`, `note`) VALUES (1,'国家标准全文公开系统（国家市场监督管理总局）','https://openstd.samr.gov.cn/bzgk/gb/std_list','2026-09-19','标准号、名称、状态与发布/实施日期均取自国家市场监督管理总局「国家标准全文公开系统」查询结果，链接为该系统的标准详情页，可点开核对。')
  ON DUPLICATE KEY UPDATE source=VALUES(source), source_url=VALUES(source_url), fetched_at=VALUES(fetched_at), note=VALUES(note);

INSERT INTO standard_ref (std_no, name, status, published, implemented, detail_url, page_standard, http_code, date_note, sort_no) VALUES
  ('GB 26860-2011','电力安全工作规程 发电厂和变电站电气部分','现行','2020-12-14','2012-06-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=A42F6AA478EEC5C7F8C9E1745C9204E6','GB 26860-2011',200,'实施日期取自该系统标准查询列表页（详情页未单列）',1)
, ('GB 46768-2025','有限空间作业安全技术规范','现行','2025-10-31','2026-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=C26BA1B610497F860D280ACF929D3F7D','GB 46768-2025',200,'',17)
, ('GB/T 14285-2023','继电保护和安全自动装置技术规程','现行','2023-11-27','2024-03-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0F1C15A59731267D3A756D6AFBB32841','GB/T 14285-2023',200,'',2)
, ('GB/T 16927.1-2011','高电压试验技术 第1部分：一般定义及试验要求','现行','2011-12-30','2012-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=E39F8AB18D7473E3EF0242BF357E158F','GB/T 16927.1-2011',200,'',11)
, ('GB/T 16927.2-2013','高电压试验技术 第2部分：测量系统','现行','2012-12-11','2013-07-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=27CE4F25FDAA76A32624751261F300A3','GB/T 16927.2-2013',200,'',12)
, ('GB/T 16927.3-2010','高电压试验技术 第3部分: 现场试验的定义及要求','现行','2010-11-10','2011-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=4DC323C0A451B5BCD3C4A253F98CD200','GB/T 16927.3-2010',200,'',13)
, ('GB/T 22390.6-2026','高压直流输电系统控制与保护设备 第6部分：换流站暂态故障录波装置','现行','2026-01-28','2026-08-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=68FDCEA373435B45706128B653DECEAC','GB/T 22390.6-2026',200,'',16)
, ('GB/T 2900.19-2022','电工术语 高电压试验技术和绝缘配合','现行','2022-10-14','2023-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=163A324C2A1AA08033AEC5C103BD22DE','GB/T 2900.19-2022',200,'',15)
, ('GB/T 40096.6-2024','就地化继电保护装置技术规范 第6部分：母线保护','现行','2024-04-25','2024-11-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=D1EB2F7470668EF4A5BDC115D3745559','GB/T 40096.6-2024',200,'',18)
, ('GB/T 40096.7-2024','就地化继电保护装置技术规范 第7部分：变压器保护','现行','2024-04-25','2024-11-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=C1558AE3A892BC5E64C884D214A1F086','GB/T 40096.7-2024',200,'',19)
, ('GB/T 40584-2021','继电保护整定计算软件及数据技术规范','现行','2021-10-11','2022-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=78304C8B291E0152CA22842D09346F84','GB/T 40584-2021',200,'',4)
, ('GB/T 40599-2021','继电保护及安全自动装置在线监视与分析技术规范','现行','2021-10-11','2022-05-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8FC4D0493F797D161B500AD4DE613DA4','GB/T 40599-2021',200,'',3)
, ('GB/T 42150.1-2022','就地化继电保护装置检测规范 第1部分：通用部分','现行','2022-12-30','2023-07-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=58C83BFF5DD3B47001FF04D0CC229D28','GB/T 42150.1-2022',200,'',20)
, ('GB/T 45568-2025','继电保护信息规范','现行','2025-04-25','2025-08-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=BAF2FBE24A61528D4EAC494DBFB27088','GB/T 45568-2025',200,'',5)
, ('GB/T 45906.1-2025','变电站二次系统 第1部分：通用要求','现行','2025-08-01','2026-02-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=30ED28E6A704B887BF73A32C60156C09','GB/T 45906.1-2025',200,'',7)
, ('GB/T 45906.10-2025','变电站二次系统 第10部分：试验与检测','现行','2025-08-01','2026-02-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=D588D59E03B68F5F0AED89398FED4E48','GB/T 45906.10-2025',200,'',10)
, ('GB/T 45906.5-2025','变电站二次系统 第5部分：保护控制及相关设备','现行','2025-08-01','2026-02-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=8E846A173E7C2AAD567131F9593CE2CF','GB/T 45906.5-2025',200,'',8)
, ('GB/T 45906.8-2025','变电站二次系统 第8部分：电气操作防误','现行','2025-08-01','2026-02-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=EE41626FE56DF4D1F7E6A6A3E1024E93','GB/T 45906.8-2025',200,'',9)
, ('GB/T 7261-2026','继电保护和安全自动装置基本试验方法','即将实施','2026-07-02','2027-02-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=0A5C12F07DE543989ACEA40A87B09FE9','GB/T 7261-2026',200,'',6)
, ('GB/T 7354-2018','高电压试验技术 局部放电测量','现行','2018-09-17','2019-04-01','https://openstd.samr.gov.cn/bzgk/gb/newGbInfo?hcno=E9ADDD16BFDDB5B5CF5328B15E6EBE4F','GB/T 7354-2018',200,'',14)
  ON DUPLICATE KEY UPDATE name=VALUES(name), status=VALUES(status), published=VALUES(published), implemented=VALUES(implemented), detail_url=VALUES(detail_url), page_standard=VALUES(page_standard), http_code=VALUES(http_code), date_note=VALUES(date_note), sort_no=VALUES(sort_no);
