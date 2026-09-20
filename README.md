# CPU 联动音量调节器 (CPU_VolumeControl)

这是一个基于 Python 的 Windows 桌面小工具。它可以根据当前系统的 CPU 占用率自动调节系统音量。CPU 占用越高，音量越大。支持系统托盘、多语言、自定义音量上限。

## 功能特点
- 根据 CPU 占用率联动调整音量
- 可拖动滑块设置音量上限
- 支持最小化到系统托盘，不占用任务栏
- 托盘右键快捷操作，内置快捷音量上限
- 支持中英文自动切换
- 窗口和弹窗居中显示

## 截图
<!-- ![界面截图](screenshot.png) -->
<img width="400" height="320" alt="屏幕截图 2026-09-20 221532" src="https://github.com/user-attachments/assets/3baea7fb-1c03-4a9d-ab95-28dea3bb2cd7" />

## 如何运行
1. 确保你安装了 Python 3.8 以上版本。
2. 安装依赖：`pip install -r requirements.txt`
3. 运行程序：`python cpu_volume_control.py`

## 如何打包成 exe
在终端运行：
`pyinstaller -F -w -i icon.ico --add-data "icon.ico;." cpu_volume_control.py`

## 开源协议
MIT License
