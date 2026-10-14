# 交接协议与信任边界

## 可信输入

manifest 必须由控制端 `prepare` 创建，哈希保存于已有任务的可信记录。`--expect-sha256` 是该记录的固定值。把 worker 返回的 manifest 与同一 worker 返回的哈希相比较，不能建立可信性。

manifest 包含 run ID、固定输入路径、目标目录、文件大小和 SHA256，以及原来源入口和捕获时解析路径。生成的 manifest 会带本地路径，属于本次任务内部证据，不要作为示例公开。

输入最多 16 份、每份最多 32 MiB。`prepare` 拒绝覆盖现有 run 目录。读取失败留下的诊断目录不是发送成功的证据。

## 接收端回执

`VERIFIED_HANDOFF_V1` 是本公版约定的固定协议标签，不是账号身份或权限证明。

````text
#V family=verified-handoff run=<run_id> ts=<UTC ISO time>
VERIFIED_HANDOFF_V1
```json
{"run_id":"<run_id>","manifest_sha256":"<pinned hash>","phase":"complete","errors":[]}
```
````

只在限定动作结束后交 `phase=complete`。它表示 worker 结束，不代表验收通过。`errors` 必须存在且为字符串列表；遗漏、重复字段或非完整阶段均不视为终态成功。

## 控制端

通过原传输获取可信接收者、message ID、时间、原 run 的结果。包内 `assess_report(contract, run_id, agent_id, sent_ms, text, meta)` 可结合这些**控制端核验的元数据**检查回执；不要把 worker 自填元数据当身份认证。

检查同 run 的完整回执时，普通补充说明不应遮住更早的完整证据；多个结构化结果矛盾时核对来源，不挑一个好看的结果。无平台消息读取器随包附带，真实身份识别和消息选择仍由原传输负责。

`verify` 核对本地固定输入与目标真实字节；拒绝目标缺失、损坏及以链接冒充复制。它不是远端存储扫描器，也不能证明同路径的文件在另一台机器存在。跨机路径必须由原传输确认，不能假定两台机器的相同路径共享文件。

## 状态

- `FILES_VERIFIED_MEMORY_UNVERIFIED`：捕获的文件版本已送达；没有原生记忆验证。
- `FILES_VERIFIED_SOURCE_ADVANCED_MEMORY_UNVERIFIED`：捕获版本已送达，但原来源已推进或入口变化。
- `FILES_NOT_VERIFIED`：存在缺失、损坏或输入契约错误。
- `MANIFEST_PIN_MISMATCH`：manifest 与控制端保存的固定哈希不一致。
- `UNKNOWN_OUTCOME`：发送器状态，由原任务保存；本包不启动重试。

CLI 的 `prepare` 成功表示快照已建立；`verify` 成功只表示字节检查通过，带 `--require-current` 时还要求来源当前。退出码 2 表示该命令未通过检查或输入错误。错误结果以 JSON 输出；不要把退出码 0 映射为业务任务完成。

发送意图持久化、单 writer、幂等键及重启恢复由原任务层维护，不由这个库实现。文件检查是时间点证据，不提供恶意并发写入防护、数字签名或 exactly-once 网络保证。原有授权和安全限制始终优先。
