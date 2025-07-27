# AstrBot 蔚蓝档案学生生日提醒

这是一个基于 AstrBot 框架，实现Blue Archive学员生日提醒的插件。

### 💽安装

---

在AstrBot插件市场安装插件后，通常情况下，AstrBot大概会自动解决依赖问题（罢

如果载入插件时提示例如 `No module named 'zipfile'` ，可能是依赖未安装

此时需要进入AstrBot Web控制台——右上角 `安装 Pip 库` ，并填入安装 `croniter` 、 `aiohttp` 、 `asyncio` 库。

### 使用方法

---

- 命令：

​	`/ba生日`        手动获取**当天**学生生日情况

​	`/ba本周生日` 获取**本周**学生生日情况

​	`/ba数据更新` 手动更新学生数据

<br>

- 配置：

  1. 开启提醒群 [列表]

     填写需要提醒的群聊唯一标识符sid。不是群号，不要填写 " `1919810114` " 之类的纯群号，唯一标识符可以向群聊发送 `/sid` 以获取，发送后，您可能会收到如下内容：

     ```text
     SID: aiocqhttp:GroupMessage:1919810114 此 ID 可用于设置会话白名单。
     /wl <SID> 添加白名单, /dwl <SID> 删除白名单。
     
     UID: 1145141919 此 ID 可用于设置管理员。
     /op <UID> 授权管理员, /deop <UID> 取消管理员。
     ```

     其中的 `aiocqhttp:GroupMessage:1919810114` 即为唯一标识符，填入配置列表即可。

<details>
<summary>❗若开启了「会话隔离」，展开此处继续查看</summary>

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;如果开启了会话隔离(unique_session)，您的唯一标识符SID可能会有所不同，向群聊发送 `/sid` 后，您可能会收到如下内容：
<pre><blockcode>
SID: aiocqhttp:GroupMessage:7210721072_1919810114 此 ID 可用于设置会话白名单。
/wl <SID> 添加白名单, /dwl <SID> 删除白名单。

UID: 7210721072 此 ID 可用于设置管理员。
/op <UID> 授权管理员, /deop <UID> 取消管理员。

当前处于独立会话模式, 此群 ID: 1919810114, 也可将此 ID 加入白名单来放行整个群聊。
</blockcode></pre>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;此时，您需要将 `GroupMessage:` 后面的那一长串内容（也就是7210721072_1919810114这段，不同消息平台格式可能不同，例如WechatPadPro端可能会是1919810114@chatroom#wxid_0d000721homo14）一起删除掉

然后在将消息里提到的`当前处于独立会话模式, 此群 ID: 1919810114`中的ID，放到`GroupMessage:` 的后面，使其变为正常的 `aiocqhttp:GroupMessage:1919810114` 格式，填入配置列表即可。
</details>

  2. 是否带学生图片 [布尔值]

     开启状态时，发送当天/本周学生生日时带上学生的图片。

  3. 每日提醒时间 [文本]

     填写每日提醒时间，格式为 HH:MM ，例如：`8:00`，`13:00` 等，冒号要用英文的！



### 叠甲

---

本项目得到了DeepSeek与通义灵码的大力支持（大雾（ Python小白一只，有点屎山，有问题尽管提Issue，求轻点喷QAQ（）

## 支持

[AstrBot 帮助文档](https://astrbot.app)

本项目数据源： [基沃托斯古书馆](https://kivo.wiki)
