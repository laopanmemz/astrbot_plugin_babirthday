import asyncio
import json
import os.path
import datetime
import shutil
import aiohttp
import croniter
import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain

@register("astrbot_plugin_babirthday", "laopanmemz", "一个Blue Archive学员生日提醒的插件。", "1.2.1")
class Birthday(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.api = "https://api.kivo.wiki/api/v1/data/students"
        self.config = config
        self.path = os.path.join("data", "plugins", "astrbot_plugin_babirthday")
        self.data_path = os.path.join(self.path, "birthday.json")
        self.isphoto = self.config.get("isphoto", True)
        self.group_ids = self.config.get("list", [])
        self.execute_time = self.config.get("time", "0:0")
        self.daily = asyncio.create_task(self.daily_task())
        self.weekly = asyncio.create_task(self.weekly_task())
        self.data_update_lock = asyncio.Lock()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        try:
            if not os.path.exists(self.data_path):
                asyncio.create_task(self.get_birthstudata())
            logger.info("✅学生数据更新成功！")
        except Exception as e:
            logger.error(str(e))

    async def get_weekbirthday(self):
        """从API中返回本周生日学生（返回为学生ID）"""
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api + "/birthday/week", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                weekbirthday = await resp.json()
        students = weekbirthday["data"]["students"]
        return students

    async def get_birthstudata(self):
        """使用返回到的ID，去请求获得学生详细信息，把本周学生的基本信息存在json内，并拉取学生头像"""
        async with self.data_update_lock:
            data = []
            students_list = await self.get_weekbirthday()
            if os.path.exists(os.path.join(self.path, "avatar")):
                shutil.rmtree(os.path.join(self.path, "avatar")) # 这一步先把原来的旧数据清空
            if not os.path.exists(os.path.join(self.path, "avatar")):
                os.mkdir(os.path.join(self.path, "avatar")) # 确认删干净后，再重新建立新目录
            async with aiohttp.ClientSession() as session:
                for student in students_list:
                    async with session.get(self.api + "/" + str(student), timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        req = await resp.json()
                    id = req["data"]["id"]
                    name = req["data"]["given_name"]
                    avatar = None
                    for i in req["data"]["skin_list"]:
                        if i.get("id") == id:
                            avatar = i.get("avatar")
                    birthday = req["data"]["birthday"]
                    data.append({"id": id, "avatar": avatar, "name": name, "birthday": birthday})
                    if avatar:
                        try:
                            async with session.get(f"https:{avatar}") as response:
                                if response.status == 200:
                                    avatar_path = os.path.join(self.path, "avatar", f"{id}.png")
                                    with open(avatar_path, 'wb') as f:
                                        f.write(await response.read())
                                else:
                                    logger.error(f"下载头像失败，状态码: {response.status}, ID: {id}")
                        except Exception as e:
                            logger.error(f"下载头像图片时出错: {e}, ID: {id}")
            with open(os.path.join(self.path, "birthday.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info("✅学生数据更新成功！")

    async def weekly_task(self):
        """使用cron表达式的每周任务"""
        # cron表达式: "0 0 * * 1" 表示每周一0点执行
        cron = croniter.croniter("0 0 * * 1", datetime.datetime.now())
        while True:
            try:
                # 获取下一次执行时间
                next_run = cron.get_next(datetime.datetime)
                now = datetime.datetime.now()
                sleep_seconds = (next_run - now).total_seconds()
                logger.info(f"下次执行每周任务时间: {next_run}，等待 {sleep_seconds} 秒")
                await asyncio.sleep(sleep_seconds)

                # 执行数据拉取
                asyncio.create_task(self.get_birthstudata())
                logger.info("每周数据拉取完成")

                # 等待一小段时间避免重复执行
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"每周定时任务执行失败: {e}")
                await asyncio.sleep(300)

    async def daily_task(self):
        """使用cron表达式的每日任务"""
        # 解析配置的时间
        hour, minute = map(int, self.execute_time.split(":"))
        # 构造cron表达式: "minute hour * * *"
        cron_expression = f"{minute} {hour} * * *"
        # 创建cron迭代器
        cron = croniter.croniter(cron_expression, datetime.datetime.now())
        while True:
            try:
                # 获取下一次执行时间
                next_run = cron.get_next(datetime.datetime)
                now = datetime.datetime.now()
                sleep_seconds = (next_run - now).total_seconds()
                logger.info(f"下次执行每日任务时间: {next_run}，等待 {sleep_seconds} 秒")
                await asyncio.sleep(sleep_seconds)
                # 添加5秒延时，确保weekly_task先执行
                await asyncio.sleep(5)
                await self.today_birthdays()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"定时任务执行失败: {e}")
                await asyncio.sleep(300)

    async def today_birthdays(self): # 发送生日提醒
        """定时发送今日生日提醒"""
        # 等待任何正在进行的数据更新完成
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month:02d}-{today.day:02d}"
        for student in data:
            if student.get("birthday") == today_str:
                id = student.get("id")
                name = student.get("name")
                avatar_path = os.path.join(self.path, "avatar", f"{id}.png")
                if self.isphoto and os.path.exists(avatar_path):
                    message_chain = MessageChain().message(f"🎉今天是 {name} 的生日！").file_image(avatar_path)
                else:
                    message_chain = MessageChain().message(f"🎉今天是 {name} 的生日！")
                for group_id in self.group_ids:
                    try:
                        await self.context.send_message(group_id, message_chain)
                        logger.debug(f"已发送提醒: {group_id}：{message_chain}")
                    except Exception as e:
                        logger.error(f"发送群消息失败: {e}")
            else:
                continue

    @filter.command("ba数据更新")
    async def update_students_command(self, event: AstrMessageEvent):
        """手动对学生数据进行更新"""
        try:
            asyncio.create_task(self.get_birthstudata())
            yield event.plain_result("✅学生数据更新成功！")
        except Exception as e:
            yield event.plain_result(str(e))

    @filter.command("ba生日")
    async def get_birthday(self, event: AstrMessageEvent):
        """手动拉取学员生日"""
        found = False
        chain = []
        # 等待任何正在进行的数据更新完成
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month:02d}-{today.day:02d}"
        for student in data:
            if student.get("birthday") == today_str:
                id = student.get("id")
                name = student.get("name")
                avatar_path = os.path.join(self.path, "avatar", f"{id}.png")
                if self.isphoto and os.path.exists(avatar_path):
                    chain.extend([
                        Comp.Plain(f"🎉今天是 {name} 的生日！"),
                        Comp.Image.fromFileSystem(avatar_path)
                    ])
                else:
                    chain.extend([f"🎉今天是 {name} 的生日！"])
                yield event.chain_result(chain)
                found = True
            else:
                continue
        if not found:
            yield event.plain_result("⏳今天没有学员过生日哦。")

    @filter.command("ba本周生日")
    async def week_birthdays(self, event: AstrMessageEvent):
        """输出本周剩余天数的学生生日"""
        # 等待任何正在进行的数据更新完成
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        # 获取当前日期
        today = datetime.date.today()
        # 计算本周一的日期
        monday = today - datetime.timedelta(days=today.weekday())
        # 生成本周所有日期
        week_dates = [monday + datetime.timedelta(days=i) for i in range(7)]
        # 格式化日期字符串列表
        date_strings = [f"{d.month:02d}-{d.day:02d}" for d in week_dates]

        birthday_dict = {}
        for student in data:
            if birthday := student.get("birthday"):
                birthday_dict.setdefault(birthday, []).append(student)
        # 生成本周生日学生列表
        ordered_results = []
        for date_str in date_strings:
            if students := birthday_dict.get(date_str):
                # 判断日期是否过了
                is_past = week_dates[date_strings.index(date_str)] < today
                is_today = week_dates[date_strings.index(date_str)] == today
                for student in students:
                    ordered_results.append((date_str, student, is_past, is_today))

        total_count = len(ordered_results)

        # 构建消息链
        chain = []
        if total_count == 0:
            chain.append(Comp.Plain("⏳本周没有学员过生日哦~"))
        else:
            # 计算已过和未过生日的学生数量
            past_count = sum(1 for _, _, is_past, is_today in ordered_results if is_past)
            future_count = sum(1 for _, _, is_past, is_today in ordered_results if not is_past and not is_today)

            chain.append(Comp.Plain(f"🎂本周生日学员列表：\n"))
            chain.append(Comp.Plain(
                f"本周共有{total_count}个学生过生日\n已过{past_count}位，未过{future_count}位\n\n"))

            # 按日期顺序显示学生信息
            for date_str, student, is_past, is_today in ordered_results:
                status = ""
                if is_today:
                    status = "（🎉就在今天！）"
                elif is_past:
                    status = "（已过）"
                else:
                    status = "（未过）"

                if self.isphoto:
                    avatar_path = os.path.join(self.path, "avatar", f"{student['id']}.png")
                    if os.path.exists(avatar_path):
                        chain.extend([
                            Comp.Plain(f"- {student['name']} ({date_str}) {status}\n"),
                            Comp.Image.fromFileSystem(avatar_path)
                        ])
                    else:
                        chain.append(Comp.Plain(f"- {student['name']} ({date_str}) {status}\n"))
                else:
                    chain.append(Comp.Plain(f"- {student['name']} ({date_str}) {status}\n"))

        yield event.chain_result(chain)
        event.stop_event()
        return

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        self.daily.cancel()
        self.weekly.cancel()
