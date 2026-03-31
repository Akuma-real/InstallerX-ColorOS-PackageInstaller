# InstallerX ColorOS PackageInstaller Module

这个仓库不是 `InstallerX-Revived` 源码仓库，而是一个面向 ColorOS 的包装仓库。

它的目标只有一个：从上游 `wxxsfxyzm/InstallerX-Revived` 的最新或指定 `pre-release` tag 拉取源码，重新构建为系统包名 `com.android.packageinstaller`，再打包成可刷入的系统安装器替换模块。

## 产物

工作流固定输出四个文件：

- `InstallerX-ColorOS-online-<version>.apk`
- `InstallerX-ColorOS-offline-<version>.apk`
- `InstallerX-ColorOS-Module-online-<version>.zip`
- `InstallerX-ColorOS-Module-offline-<version>.zip`

`online` 和 `offline` 都会改成系统包名 `com.android.packageinstaller`，因此它们是互斥构建，不能同时刷入。

## 工作流

当前仓库提供一个手动触发工作流：

- 默认自动解析上游最新 `pre-release`
- 可通过 `upstream_tag` 指定某个现有 `pre-release` tag
- 可通过 `publish_release` 控制是否在当前仓库创建 draft release

工作流会完成这些动作：

1. 解析上游 `pre-release` 信息
2. 克隆上游源码并校验 `tag` 与提交短哈希一致
3. 使用 JDK 25 与 Gradle Wrapper 构建 `onlinePreviewRelease` 和 `offlinePreviewRelease`
4. 构建时传入：
   - `-PAPP_ID=com.android.packageinstaller`
   - `-PVERSION_NAME=<yy.MM>`
5. 读取 `output-metadata.json` 作为构建产物真值源
6. 组装 Magisk + KernelSU 兼容模块 zip
7. 校验 APK 包名、版本号、模块 zip 结构和 `module.prop`
8. 上传四个 artifact，并可选创建当前仓库 draft release

## 必需 Secrets

如果需要自定义签名，请在当前仓库配置这些 secrets：

- `SIGNING_KEY_STORE_BASE64`
- `SIGNING_STORE_PASSWORD`
- `SIGNING_KEY_ALIAS`
- `SIGNING_KEY_PASSWORD`

如果这些签名变量缺失，上游项目会退回默认 debug keystore。对“替换系统安装器”这种用途，不建议使用 debug 签名发布给别人刷入。

## 模块结构

生成的模块 zip 以 zip 根目录直接包含这些内容：

- `module.prop`
- `customize.sh`
- `action.sh`
- `service.sh`
- `uninstall.sh`
- `META-INF/com/google/android/update-binary`
- `META-INF/com/google/android/updater-script`
- `system/priv-app/PackageInstaller/PackageInstaller.apk`
- `system/priv-app/PackageInstaller/lib/<abi>/*.so`

目录结构参考了仓库内的样例模块 `com.android.packageinstaller-online2.3.2.zip`，但不会强求字节级一致。

## 限制

- 仅面向 ColorOS 这类“直接替换系统安装器 APK”场景
- 不负责 AOSP / 类原生系统需要的 `privapp-permissions-platform.xml`
- 不会自动定时追上游，只支持人工触发
- 只接受上游 `pre-release` tag；如果 tag 不是 `pre-release`，工作流会直接失败

## 高风险提示

替换系统安装器属于高风险操作。

- 这是“修改 `/system` 文件”的范畴
- 需要 metamodule 支持，例如 `meta-overlayfs`
- 没有这层支持时，模块本体不一定能正常覆盖 `/system`
- 错误刷入可能导致无法开机、系统异常、安装器崩溃或系统组件不可用

请只在你明确知道自己在做什么、并且具备恢复手段时使用。

