# WeFlow 时间回拨启动套件 开发说明

> 组成：临时启动WeFlow_时间回拨.bat（项目根目录）+ scripts/weflow_verify_runasdate.py
> 创建：2026-10-12 | 归属：Akasha-Wechat_RC

## 1. 解决什么问题

WeFlow 上游 hicccc77/WeFlow 的 wcdb_api.dll 内置了授权时间炸弹（到期后
InitProtection 返回 -101，弹窗"初始化失败"，数据库层整体不可用）。本机
到期点：2026-10-01 傍晚。社区确认这是防破解机制（issue #1226/#1227），
作者未修。SSE 推送与联系人接口不依赖 WCDB，所以机器人收发不受影响，
但历史查询、图片取证、本补偿工具的 --find/验证全部依赖数据库。

方案：用 RunAsDate（NirSoft，x64）把 WeFlow 进程内时钟**冻结**在
2026-09-30 12:00:00（到期点之前）。静态时钟不走表，到期点永远不会
到来——**无需定时重启**。系统时钟不动，AstrBot/桥接/微信均不受影响。

## 2. 文件与职责

| 文件 | 职责 |
|---|---|
| 临时启动WeFlow_时间回拨.bat | 一键启动：RunAsDate 拉起 WeFlow + 等 25s + 调验证脚本 |
| scripts/weflow_verify_runasdate.py | 验证器：contacts 200 -> 用真实群测 messages，200=恢复，500=未生效 |
| vendor/runasdate/RunAsDate.exe | NirSoft RunAsDate x64 1.41（手动下载，gitignore） |

## 3. bat 的三个坑（改这个文件前必读）

1. **编码**：cmd 按 GBK 解析 bat。UTF-8 中文或 LF-only 换行都会导致解析错乱
   （误报"找不到文件"后闪退）。本文件是**纯 ASCII + CRLF**，改完自查：
   od -c 文件头应为 40 65 63 68 6f ... 0d 0a。
2. **if 块内的裸右括号**：echo 行里的 ) 会提前闭合代码块（报"此时不应有
   then"）。块内提示文本用 [] 代替 ()。
3. **find 不是 Windows 的**：PATH 里有 Git 的 GNU find 会抢占，必须用 findstr；
   timeout /t 在 stdin 重定向下会直接报错，延时用 ping -n 26 127.0.0.1。

## 4. RunAsDate 调用语法（readme 权威）

    RunAsDate.exe {/immediate} [dd\mm\yyyy] {hh:mm:ss} [Program] {params}

不带 /movetime 即静态时钟。/immediate 必须加：WeFlow 在内核早期就读时间，
默认模式注入太晚会漏钩。注意验证脚本输出乱码属管道编码问题，实际控制台正常。

## 5. 验证判定（weflow_verify_runasdate.py）

- contacts 接口不依赖 WCDB，作为 WeFlow 活性探针（401=token 问题，000=没起来）；
- messages 接口依赖 WCDB：500=时间回拨未生效（RunAsDate 没钩住），200=已恢复；
- 判定只看这两个 HTTP 码，与 wcdb.log 无关——回拨生效后 WeFlow 自己写日志
  的时间戳也是假时间（冻结在 9/30），按真实时间窗口 grep 会"看不到新行"。

## 6. 已验证事实（2026-10-12/13）

- 计划任务逃出 agent 沙箱后实测：WeFlow 十进程存活、5031 监听、messages 200；
- DSH agent 沙箱的作业树会在命令结束时回收所有派生进程：start "" 分离进程秒死、
  start /wait 阻塞主 bat 可存活、RunAsDate 在沙箱内派生不出目标进程——
  **你双击运行（explorer 作业树）没有这些限制**；
- 风险提示：DLL 里有"违规修改已被加密存证"文案，作者理论上有防篡改检测，
  时间回拨不碰文件字节，风险低于二进制 patch（未实施 patch）。

## 7. 与其他工具的关系

- scripts/reply_missed.py（漏收补偿）依赖数据库可用：WeFlow 被 -101 卡住时，
  先跑本套件拉起 WeFlow，再跑补偿工具；
- 桥接 SSE 10s 自动重连，WeFlow 拉起后机器人自动恢复，无需重启桥接。