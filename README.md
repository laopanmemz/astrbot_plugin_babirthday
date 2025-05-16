# AstrBot 蔚蓝档案学生生日提醒

这是一个基于 AstrBot 框架，实现Blue Archive学员生日提醒的插件。

### 💽安装

---

在AstrBot插件市场安装插件后，通常情况下，AstrBot大概会自动解决依赖问题（罢

如果载入插件时提示例如 `No module named 'zipfile'` ，可能是依赖未安装

此时需要进入AstrBot Web控制台——右上角 `安装 Pip 库` ，并安装 `gitpython` 、 `zipfile` 、 `asyncio` 库。

或者在插件目录打开cmd，执行 `pip install -r requirements.txt` ，以补齐依赖。

### 使用方法

---

<u>**正常情况下，安装插件后会自动解压SchaleDB.zip，如未正常解压，进入插件文件夹，将SchaleDB.zip解压，解压后会得到SchaleDB单文件夹**</u>

<u>**文件夹内有".git"（隐藏）、"data"、"images"三个文件夹。**</u>

- 命令：

​	`/ba生日`        手动获取**当天**学生生日情况

​	`/ba本周生日` 获取**本周**学生生日情况

​	`/ba数据更新` 手动更新学生数据

<br>

- 配置：

  1. 开启提醒群 [列表]

     填写需要提醒的群聊唯一标识符sid。不是群号，不要填写 “ `1919810114` ” 之类的纯群号，唯一标识符可以向群聊发送 `/sid` 以获取，发送后，您可能会收到如下内容：

     ```text
     SID: aiocqhttp:GroupMessage:1919810114 此 ID 可用于设置会话白名单。
     /wl <SID> 添加白名单, /dwl <SID> 删除白名单。
     
     UID: 1145141919 此 ID 可用于设置管理员。
     /op <UID> 授权管理员, /deop <UID> 取消管理员。
     ```


  ​	其中的 `aiocqhttp:GroupMessage:1919810114` 即为唯一标识符，填入配置列表即可。

  2. 是否带学生图片 [布尔值]

     开启状态时，发送当天/本周学生生日时带上学生的图片。

  3. 每日提醒时间 [文本]

     填写每日提醒时间，格式为 HH:MM ，例如：`8:00`，`13:00` 等，冒号要用英文的！

### 常见问题

------

1. 执行 `/ba数据更新` 时抛出 `唔嘿~仓库貌似不存在哦，请查看README文档克隆仓库。` 或者 `唔嘿~仓库似乎没有初始化，请查看README文档重新克隆仓库哦。` 异常时，说明你SchaleDB仓库不完整或者被删除了，进入插件目录，删除SchaleDB文件夹后，在插件目录执行以下命令重新克隆仓库：

   ``````shell
   # 初始化仓库
   git init SchaleDB
   
   # 进入仓库目录
   cd SchaleDB
   
   # 添加远程仓库 （如果因网络问题无法克隆可加上镜像加速下载地址前缀）
   git remote add origin https://github.com/SchaleDB/SchaleDB
   
   # 启用稀疏检出（全克隆的话也行，跳过这行和下一行即可，只不过这样的话整个文件夹可能会有一点大）
   git config core.sparseCheckout true
   
   # 检出要用到的数据文件/文件夹 （Windows端请删除下面的""双引号）
   echo "data/cn/students.json" >> .git/info/sparse-checkout
   echo "images/student/icon/" >> .git/info/sparse-checkout
   
   #浅克隆main分支仓库
   git pull --depth 1 origin main
   ``````

   完成克隆后，再次执行 `/ba数据更新` 大抵应该就能正常拉取仓库更新了（

2. 遇到抛出 `从 SchaleDB 仓库拉取数据失败！请参阅README文档常见问题以解决。` 的错误，大多数是因为网络问题，可通过以下两种方法，自行修改远程仓库链接，加上加速镜像前置地址即可。

   第一种：打开插件文件夹/.git文件夹（文件夹默认为隐藏状态），找到config文件，修改url行的地址即可。

   ```
   [remote "origin"]
   	url = https://github.com/laopanmemz/astrbot_plugin_babirthday.git
   ```

   第二种：打开插件文件夹目录，进入Schale文件夹，在此文件夹打开cmd，然后执行

   `git remote set-url origin [新地址]`  即可。

#### 镜像加速地址

---

> 可前往 [加速站状态页](https://status.akams.cn/status/services) 此处，找到 `Github 公益代理`  栏，选一个能用的
>
> 加速地址格式：加速链接 + 完整Github 仓库链接，例如：
>
> **`https://github.moeyy.xyz/https://github.com/SchaleDB/SchaleDB`**

### 叠甲

---

本项目得到了DeepSeek与通义灵码的大力支持（大雾（ Python小白一只，有点屎山，有问题尽管提Issue，求轻点喷QAQ（）

## 支持

[AstrBot 帮助文档](https://astrbot.app)

本项目数据源： [SchaleDB仓库](https://github.com/SchaleDB/SchaleDB)
