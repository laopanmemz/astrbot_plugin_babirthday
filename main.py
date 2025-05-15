import json
import os.path
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import astrbot.api.message_components as Comp
from git import Repo, Git
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain

class DataDownloadError(Exception): # 自定义数据下载异常类
    pass

@register("astrbot_plugin_babirthday", "laopanmemz", "一个Blue Archive学员生日提醒的插件。", "1.0.0")
class Birthday(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.path = os.path.join("data", "plugins", "astrbot_plugin_babirthday") # 将路径全部写入变量
        self.schaledb_repo = "https://github.com/SchaleDB/SchaleDB.git"
        self.stu_icon = os.path.join("images", "student", "icon")
        self.stu_json = os.path.join("data", "cn", "students.json")
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai") # 新建调度器
        self.isphoto = self.config.get("isphoto", True)
        self.group_ids = self.config.get("group_id", [])  # 保存群组ID列表

    async def today_birthdays(self): # 发送生日提醒
        """定时发送今日生日提醒"""
        data_path = os.path.join(self.path, "SchaleDB", self.stu_json)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month}月{today.day}日"
        today_students = []
        for student in data:
            if student.get("Birthday") == today_str:
                today_students.append(student)
        if today_students:
            shortest_student = min(today_students, key=lambda x: len(x["Name"]))
            student_id = shortest_student["Id"]
            student_name = shortest_student["Name"]
            image_path = os.path.join(self.path, "SchaleDB", self.stu_icon, f"{student_id}.webp")
            if self.isphoto and os.path.exists(image_path):
                message_chain = MessageChain().message(f"🎉今天是 {student_name} 的生日！").file_image(image_path)
            else:
                message_chain = MessageChain().message(f"🎉今天是 {student_name} 的生日！")
            for group_id in self.group_ids:
                try:
                    await self.context.send_message(group_id, message_chain)
                except Exception as e:
                    logger.error(f"发送群消息失败: {e}")

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        # 配置定时任务
        try:
            execute_time = self.config.get("time", "0:0")
            hour, minute = map(int, execute_time.split(":"))
            self.scheduler.add_job(
                self.today_birthdays,
                CronTrigger(hour=hour, minute=minute)
            )
            self.scheduler.start()
            logger.info(f"定时任务已启动: {hour:02}:{minute:02}")
        except Exception as e:
            logger.error(f"定时任务配置失败: {e}")

    async def update_students(self):
        """更新所有学生数据"""
        git = Git(os.path.join(self.path, "SchaleDB"))
        repo = Repo(os.path.join(self.path, "SchaleDB"))
        git.config("core.sparseCheckout", "true")
        if not os.path.exists(os.path.join(self.path, "SchaleDB")):
            raise Exception("唔嘿~仓库貌似不存在哦，请查看README文档克隆仓库。")
        if not os.path.exists(os.path.join(self.path, "SchaleDB", ".git")):
            raise Exception("唔嘿~仓库似乎没有初始化，请查看README文档重新克隆仓库哦。")
        try:
            repo.git.pull("origin", "main", depth=1, force=True)
        except Exception as e:
            raise DataDownloadError(f"从 SchaleDB 仓库拉取数据失败！请参阅README文档常见问题以解决。{str(e)}")
        return

    @filter.command("ba数据更新")
    async def update_students_command(self, event: AstrMessageEvent):
        """手动对学生数据进行更新"""
        try:
            await self.update_students()
            yield event.plain_result("✅学生数据更新成功！")
        except DataDownloadError as e:
            yield event.plain_result(str(e))

    @filter.command("ba生日")
    async def get_birthday(self, event: AstrMessageEvent):
        """手动拉取学员生日"""
        data_path = os.path.join(self.path, "SchaleDB", self.stu_json)
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        today = datetime.date.today()
        today_str = f"{today.month}月{today.day}日"
        found = False
        chain = []
        today_students = []
        for student in data:
            if student.get("Birthday") == today_str:
                today_students.append(student)
        if today_students:
            shortest_student = min(today_students, key=lambda x: len(x["Name"]))
            student_id = shortest_student["Id"]
            student_name = shortest_student["Name"]
            image_path = os.path.join(self.path, "SchaleDB", self.stu_icon, f"{student_id}.webp")
            if self.isphoto and os.path.exists(image_path):
                chain.extend([
                    Comp.Plain(f"🎉今天是 {student_name} 的生日！"),
                    Comp.Image.fromFileSystem(image_path)
                ])
            else:
                chain.extend([f"🎉今天是 {student_name} 的生日！"])
            yield event.chain_result(chain)
            found = True
        if not found:
            yield event.plain_result("⏳今天没有学员过生日哦。")


    @filter.command("ba本周生日")
    async def week_birthdays(self, event: AstrMessageEvent):
        """输出本周剩余天数的学生生日"""
        with open(os.path.join(self.path, "SchaleDB", self.stu_json), "r", encoding="utf-8") as f:
            data = json.load(f) # 读取json文件
        # 获取当前日期
        today = datetime.date.today()
        # 计算当前是本周第几天（周一为1，周日为7）
        current_weekday = today.isoweekday()
        # 计算到周日还需几天
        days_until_sunday = 7 - current_weekday
        # 生成从今天到周日的所有日期
        dates = [today + datetime.timedelta(days=i) for i in range(days_until_sunday + 1)]
        # 格式化日期为"X月X日"的字符串列表
        date_strings = [f"{d.month}月{d.day}日" for d in dates]
        # 构建生日字典
        birthday_dict = {}
        for student in data:
            if birthday := student.get("Birthday"):
                birthday_dict.setdefault(birthday, []).append(student)
        # 生成有序结果
        ordered_results = []
        for date_str in date_strings:
            if students := birthday_dict.get(date_str):
                ordered_results.append((date_str, students))
        # 构建消息链
        chain = []
        if not ordered_results:
            chain.append(Comp.Plain("本周已经没有学员过生日了哦～🎉"))
        else:
            chain.append(Comp.Plain("🎂本周生日学员列表：\n\n"))
            for date_str, students in ordered_results:
                # 添加日期标题
                chain.append(Comp.Plain(f"\n\n📅{date_str}："))
                # 遍历当日学员
                for idx, student in enumerate(students, 1):
                    # 添加学生信息
                    if self.isphoto:
                        chain.extend([
                            Comp.Plain(f"\n{idx}. {student['Name']}"),
                            Comp.Image.fromFileSystem(os.path.join(self.path, "SchaleDB", self.stu_icon, f"{student['Id']}.webp"))
                        ])
                    else:
                        chain.extend([Comp.Plain(f"\n{idx}. {student['Name']}")])
        yield event.chain_result(chain)
        event.stop_event()
        return

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if self.scheduler and self.scheduler.running:
            await self.scheduler.shutdown()
            logger.info("定时任务已经被优雅的关闭了~")