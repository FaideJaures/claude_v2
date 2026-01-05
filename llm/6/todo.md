# 任务清单 (llm/6)

- [x] **1. 优化重组脚本 (`src/utils/unified.sh`)**
    - [x] 修改 `cat` 循环为 glob 扩展方式
    - [x] 验证脚本逻辑并处理空目录情况
- [x] **2. 修复取消按钮 (`src/utils/adb.py`)**
    - [x] 在 `Adb` 类中实现进程跟踪
    - [x] 添加 `terminate_all` 方法
    - [x] 在 `TransferManager` 和 `ReassemblyManager` 中集成取消逻辑
- [x] **3. 优化传输/恢复校验 (`src/core/transfer.py`)**
    - [x] 实现远程文件批量列表获取
    - [x] 修改 `_check_remote_file_exists` 使用本地缓存数据
    - [x] 修改 `_verify_transfer_on_device` 使用本地缓存数据
- [x] **4. 优化日志性能 (`src/main.py`)**
    - [x] 引入日志批量更新队列
    - [x] 实现异步 UI 刷新机制

    - [ ] 引入日志批量更新队列
    - [ ] 实现异步 UI 刷新机制
