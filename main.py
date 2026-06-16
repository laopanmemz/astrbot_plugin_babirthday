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

# 手动构建不包含消息隔离特征的unified_msg_origin（umo）获取方法
def get_original_umo(event: AstrMessageEvent) -> str:
    return f"{event.get_platform_name()}:{event.message_obj.type.value}:{event.message_obj.session_id}"

@register(
    "astrbot_plugin_babirthday",
    "laopanmemz",
    "一个Blue Archive学员生日提醒的插件。",
    "1.2.3",
)
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
        self.data_update_lock = asyncio.Lock()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        self.daily = asyncio.create_task(self.daily_task())
        self.weekly = asyncio.create_task(self.weekly_task())
        try:
            if not os.path.exists(self.data_path):
                asyncio.create_task(self.get_birthstudata())
            logger.info("✅学生数据更新成功！")
        except Exception as e:
            logger.error(str(e))

    async def _retry_request(self, request_factory, description="", max_retries=10):
        """带重试的网络请求包装器。
        request_factory: 无参函数，每次调用返回一个新的协程对象。
        全部重试失败后抛出异常，由调用方决定处理方式（logger.error / 返回给用户）。
        """
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return await request_factory()
            except Exception as e:
                last_error = e
                logger.warning(f"{description} 第 {attempt}/{max_retries} 次失败: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1)
        logger.error(f"{description} 全部 {max_retries} 次重试均失败: {last_error}")
        raise last_error

    async def get_weekbirthday(self):
        """从API中返回本周生日学生（返回为学生ID）"""
        async with aiohttp.ClientSession() as session:

            async def _do():
                async with session.get(
                    self.api + "/birthday/week", timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status}")
                    return await resp.json()

            weekbirthday = await self._retry_request(_do, "获取本周生日列表")
        students = weekbirthday["data"]["students"]
        return students

    async def get_birthstudata(self, check_stale=True):
        """使用返回到的ID，去请求获得学生详细信息，把本周学生的基本信息存在json内，并拉取学生头像

        check_stale: 为 True 时检查上游 API 是否已更新（ID 不重复），避免拉到旧数据。
                     每周定时任务使用 True，手动更新命令使用 False。
        全程持锁，保证期间 daily_task 的读取操作必须等待。
        """
        async with self.data_update_lock:
            # ── 步骤1: 获取本周学生 ID 列表 ──
            students_list = await self.get_weekbirthday()

            # ── 步骤2: 检查上游 API 是否已更新（仅定时任务需要）──
            if check_stale and os.path.exists(self.data_path):
                with open(self.data_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                old_ids = {s["id"] for s in old_data}
                deadline = datetime.datetime.now() + datetime.timedelta(hours=1)

                while set(students_list) & old_ids:
                    if datetime.datetime.now() >= deadline:
                        logger.warning(
                            "上游 API 超过1小时未更新（ID 仍重复），使用当前数据继续"
                        )
                        break
                    logger.info(
                        f"上游 API 尚未更新（{len(set(students_list) & old_ids)} 个 ID 重复），等待1分钟后重试..."
                    )
                    await asyncio.sleep(60)
                    students_list = await self.get_weekbirthday()

            # ── 步骤3: 数据同步 ──
            data = []

            # 清理旧头像目录
            if os.path.exists(os.path.join(self.path, "avatar")):
                shutil.rmtree(os.path.join(self.path, "avatar"))
            if not os.path.exists(os.path.join(self.path, "avatar")):
                os.mkdir(os.path.join(self.path, "avatar"))

            # 并发请求所有学生详情数据（每个请求带重试）
            async def fetch_student(session, student_id):

                async def _do():
                    async with session.get(
                        self.api + "/" + str(student_id),
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status != 200:
                            raise Exception(f"HTTP {resp.status}")
                        return await resp.json()

                return await self._retry_request(_do, f"获取学生 {student_id} 详情")

            async with aiohttp.ClientSession() as session:
                tasks = [fetch_student(session, sid) for sid in students_list]
                results = await asyncio.gather(*tasks)

            # 解析学生数据
            for req in results:
                sid = req["data"]["id"]
                name = req["data"]["given_name"]
                avatar = None
                for skin in req["data"]["skin_list"]:
                    if skin.get("id") == sid:
                        avatar = skin.get("avatar")
                birthday = req["data"]["birthday"]
                data.append(
                    {"id": sid, "avatar": avatar, "name": name, "birthday": birthday}
                )

            # 下载头像（每个带重试，失败则回退到纯文字发送）
            async with aiohttp.ClientSession() as session:
                for student in data:
                    avatar = student.get("avatar")
                    sid = student["id"]
                    if avatar:
                        try:
                            async def _do():
                                async with session.get(f"https:{avatar}") as response:
                                    if response.status == 200:
                                        return await response.read()
                                    raise Exception(f"HTTP {response.status}")
                            content = await self._retry_request(
                                _do, f"下载头像 ID:{sid}"
                            )
                            avatar_path = os.path.join(
                                self.path, "avatar", f"{sid}.png"
                            )
                            with open(avatar_path, "wb") as f:
                                f.write(content)
                        except Exception as e:
                            logger.error(f"下载头像图片时出错: {e}, ID: {sid}")
                            student["avatar"] = None  # 回退到纯文字

            with open(
                os.path.join(self.path, "birthday.json"), "w", encoding="utf-8"
            ) as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info("✅学生数据更新成功！")

    async def weekly_task(self):
        """每周一 00:00 执行：同步数据+头像"""
        while True:
            # 每次迭代重新创建 cron 对象，避免时间漂移
            cron = croniter.croniter("0 0 * * 1", datetime.datetime.now())
            next_run = cron.get_next(datetime.datetime)
            now = datetime.datetime.now()
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds < 0:
                sleep_seconds = 0
            logger.info(
                f"下次执行每周任务时间: {next_run}，等待 {sleep_seconds:.0f} 秒"
            )
            await asyncio.sleep(sleep_seconds)

            try:
                # 同步数据 + 下载所有头像（全程持锁）
                await self.get_birthstudata()
                logger.info("每周数据同步完成")
            except Exception as e:
                logger.error(f"每周定时任务执行失败: {e}")

            await asyncio.sleep(60)

    async def daily_task(self):
        """每日定时发送生日提醒。若数据正在更新（持锁），自动等待更新完成后再发送。"""
        hour, minute = map(int, self.execute_time.split(":"))
        cron_expression = f"{minute} {hour} * * *"

        while True:
            # 每次迭代重新创建 cron 对象，避免时间漂移
            cron = croniter.croniter(cron_expression, datetime.datetime.now())
            next_run = cron.get_next(datetime.datetime)
            now = datetime.datetime.now()
            sleep_seconds = (next_run - now).total_seconds()
            if sleep_seconds < 0:
                sleep_seconds = 0
            logger.info(
                f"下次执行每日任务时间: {next_run}，等待 {sleep_seconds:.0f} 秒"
            )
            await asyncio.sleep(sleep_seconds)

            try:
                # 等5秒让 weekly_task 优先抢锁，若锁被持有则阻塞等待释放
                await asyncio.sleep(5)
                await self.today_birthdays()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"每日定时任务执行失败: {e}")
                await asyncio.sleep(300)

    async def today_birthdays(self):
        """发送今日生日提醒"""
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month:02d}-{today.day:02d}"
        for student in data:
            if student.get("birthday") == today_str:
                sid = student.get("id")
                name = student.get("name")
                avatar_path = os.path.join(self.path, "avatar", f"{sid}.png")
                if self.isphoto and os.path.exists(avatar_path):
                    message_chain = (
                        MessageChain()
                        .message(f"🎉今天是 {name} 的生日！")
                        .file_image(avatar_path)
                    )
                else:
                    message_chain = MessageChain().message(f"🎉今天是 {name} 的生日！")
                for group_id in self.group_ids:
                    try:
                        await self.context.send_message(group_id, message_chain)
                        logger.debug(f"已发送提醒: {group_id}：{message_chain}")
                    except Exception as e:
                        logger.error(f"发送群消息失败: {e}")

    @filter.command("ba数据更新")
    async def update_students_command(self, event: AstrMessageEvent):
        """手动对学生数据进行更新（跳过上游 API 过期检查，立即更新）"""
        try:
            await self.get_birthstudata(check_stale=False)
            yield event.plain_result("✅学生数据更新成功！")
        except Exception as e:
            yield event.plain_result(f"❌数据更新失败: {e}")

    @filter.command("ba生日")
    async def get_birthday(self, event: AstrMessageEvent):
        """手动拉取学员生日"""
        found = False
        chain = []
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month:02d}-{today.day:02d}"
        for student in data:
            if student.get("birthday") == today_str:
                sid = student.get("id")
                name = student.get("name")
                avatar_path = os.path.join(self.path, "avatar", f"{sid}.png")
                if self.isphoto and os.path.exists(avatar_path):
                    chain.extend(
                        [
                            Comp.Plain(f"🎉今天是 {name} 的生日！"),
                            Comp.Image.fromFileSystem(avatar_path),
                        ]
                    )
                else:
                    chain.extend([Comp.Plain(f"🎉今天是 {name} 的生日！")])
                yield event.chain_result(chain)
                found = True
        if not found:
            yield event.plain_result("⏳今天没有学员过生日哦。")

    @filter.command("ba本周生日")
    async def week_birthdays(self, event: AstrMessageEvent):
        """输出本周剩余天数的学生生日"""
        async with self.data_update_lock:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        week_dates = [monday + datetime.timedelta(days=i) for i in range(7)]
        date_strings = [f"{d.month:02d}-{d.day:02d}" for d in week_dates]

        birthday_dict = {}
        for student in data:
            if birthday := student.get("birthday"):
                birthday_dict.setdefault(birthday, []).append(student)
        ordered_results = []
        for date_str in date_strings:
            if students := birthday_dict.get(date_str):
                is_past = week_dates[date_strings.index(date_str)] < today
                is_today = week_dates[date_strings.index(date_str)] == today
                for student in students:
                    ordered_results.append((date_str, student, is_past, is_today))

        total_count = len(ordered_results)
        chain = []
        if total_count == 0:
            chain.append(Comp.Plain("⏳本周没有学员过生日哦~"))
        else:
            past_count = sum(
                1 for _, _, is_past, is_today in ordered_results if is_past
            )
            future_count = sum(
                1
                for _, _, is_past, is_today in ordered_results
                if not is_past and not is_today
            )
            chain.append(Comp.Plain(f"🎂本周生日学员列表：\n"))
            chain.append(
                Comp.Plain(
                    f"本周共有{total_count}个学生过生日\n已过{past_count}位，未过{future_count}位\n\n"
                )
            )
            for date_str, student, is_past, is_today in ordered_results:
                status = ""
                if is_today:
                    status = "（🎉就在今天！）"
                elif is_past:
                    status = "（已过）"
                else:
                    status = "（未过）"
                if self.isphoto:
                    avatar_path = os.path.join(
                        self.path, "avatar", f"{student['id']}.png"
                    )
                    if os.path.exists(avatar_path):
                        chain.extend(
                            [
                                Comp.Plain(
                                    f"- {student['name']} ({date_str}) {status}\n"
                                ),
                                Comp.Image.fromFileSystem(avatar_path),
                            ]
                        )
                    else:
                        chain.append(
                            Comp.Plain(f"- {student['name']} ({date_str}) {status}\n")
                        )
                else:
                    chain.append(
                        Comp.Plain(f"- {student['name']} ({date_str}) {status}\n")
                    )

        yield event.chain_result(chain)
        event.stop_event()
        return

    @filter.command("订阅ba生日")
    async def add_sub(self, event: AstrMessageEvent):
        """订阅ba生日信息推送"""
        umo = get_original_umo(event)
        
        # 获取当前订阅列表
        sub_list = self.config.get("list", [])
        
        # 检查是否已订阅
        if umo in sub_list:
            yield event.plain_result("您已订阅过推送了。")
            return
        
        # 添加到订阅列表
        sub_list.append(umo)
        self.config["list"] = sub_list
        self.config.save_config()
        
        yield event.plain_result("✅ 成功订阅推送")

    @filter.command("退订ba生日", alias={"tdba生日"})
    async def remove_sub(self, event: AstrMessageEvent):
        """取消订阅ba生日信息推送"""
        umo = get_original_umo(event)
        
        # 获取当前订阅列表
        sub_list = self.config.get("list", [])
        
        # 检查是否已订阅
        if umo not in sub_list:
            yield event.plain_result("您还没有订阅过推送。")
            return
        
        # 从订阅列表中移除
        sub_list.remove(umo)
        self.config["list"] = sub_list
        self.config.save_config()
        
        yield event.plain_result("已取消订阅推送。")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        self.daily.cancel()
        self.weekly.cancel()
