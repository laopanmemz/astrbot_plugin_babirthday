import json
import os.path
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import astrbot.api.message_components as Comp
from git import Repo, GitCommandError
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig

class DataDownloadError(Exception): # 自定义数据下载异常类
    pass

@register("astrbot_plugin_babirthday", "laopanmemz", "一个Blue Archive学员生日提醒的插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.path = os.path.join("data", "plugin", "astrbot_plugin_babirthday") # 将路径全部写入变量
        self.schaledb_repo = "https://github.com/SchaleDB/SchaleDB"
        self.stu_icon = "images/student/icon"
        self.stu_json = "data/cn/students.json"
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai") # 新建调度器
        self.isphoto = self.config.get("isphoto", True)

    async def today_birthdays(self, event: AstrMessageEvent): # 发送生日提醒
        with open(os.path.join("data", "plugin", "astrbot_plugin_babirthday", "SchaleDB", self.stu_json), "r", encoding="utf-8") as f:
            data = json.load(f) # 读取json文件
        datetime_today = datetime.date.today() # 获取当前日期
        today = f"{datetime_today.month}月{datetime_today.day}日" # 格式化日期
        for i in data:
            if i.get("Birthday") == today: # 判断是否有生日
                Id = i.get("Id")
                Name = i.get("Name")
                # 构建富文本消息
                if self.isphoto:
                    chain = [
                        Comp.Plain(f"🎉今天是 {Name} 的生日！"),
                        Comp.Image.fromFileSystem(os.path.join("data", "plugin", "astrbot_plugin_babirthday", "SchaleDB", self.stu_icon, f"{Id}.webp"))
                    ]
                    yield event.chain_result(chain)
                else:
                    yield event.plain_result(f"🎉今天是 {Name} 的生日！")
                event.stop_event()
                return
            else:
                continue
        raise Exception("今天暂无学员过生日哦！")

    async def initialize(self, event: AstrMessageEvent):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        if not os.path.exists(os.path.join("data", "plugin", "astrbot_plugin_babirthday", "SchaleDB", self.stu_json)): # 判断是否存在students.json，如无则调用更新函数拉取
            try:
                yield self.update_students(event)
            except DataDownloadError:
                logger.error(f"从 SchaleDB 仓库拉取数据失败！所有加速链接均无法访问，请检查配置以及网络环境。")
        try:
            execute_time = self.config.get("time", "0:0")
            hour, minute = map(int, execute_time.split(":"))
            self.scheduler.add_job(self.today_birthdays,CronTrigger(hour=hour,minute=minute),args=[event])
            self.scheduler.start()
            logger.info(f"已启用定时任务：每天 {execute_time} 点更新ba生日提醒！")
        except (Exception, ValueError, KeyError) as e:
            logger.error(f"定时任务启动失败：{e}")

    async def update_students(self, event: AstrMessageEvent):
        proxies = self.config.get("proxy") # 获取配置文件中的加速链接列表
        for proxy_url in proxies:
            proxy_url = proxy_url.rstrip('/') + '/'  # 统一处理结尾斜杠
            if os.path.exists(os.path.join(self.path, "SchaleDB")): # 判断是否存在SchaleDB目录
                if os.path.exists(os.path.join(self.path, "SchaleDB", ".git")): # 如果有，则判断是否存在.git目录
                    try:
                        repo = Repo(os.path.join(self.path, "SchaleDB")) #
                        with repo.config_writer() as config:
                            config.set_value('remote "origin"', 'url', f"{proxy_url}{self.schaledb_repo}")
                        repo.remotes.origin.pull()
                        logger.error("成功从 SchaleDB 仓库更新数据！")
                        return
                    except GitCommandError:
                        logger.error(f"从 SchaleDB 仓库更新数据失败！请检查配置以及网络环境。")
                        continue
                else:
                    # 不是 Git 仓库，提示用户清理目录
                    logger.error(f"目录 SchaleDB 已存在且不是 Git 仓库，请删除目录后重试")
                    return

            else:
                # 目录不存在，初始化新仓库并使用加速链接克隆
                try:
                    repo = Repo.init(os.path.join(self.path, "SchaleDB"))
                    origin = repo.create_remote("origin", f"{proxy_url}{self.schaledb_repo}")
                    origin.fetch()
                    repo.git.config("core.sparseCheckout", "true")
                    with open(os.path.join(self.path, "SchaleDB", ".git", "info", "sparse-checkout"), "w") as f:
                        f.write(self.stu_icon + "\n")
                        f.write(self.stu_json + "\n")
                    origin.pull("main")
                    logger.info(f"使用加速链接 {proxy_url} 克隆仓库成功")
                    return
                except GitCommandError as e:
                    logger.warning(f"使用加速链接 {proxy_url} 克隆仓库失败: {e}")
                    continue
        raise DataDownloadError("从 SchaleDB 仓库拉取数据失败！所有加速链接均无法访问，请检查配置以及网络环境。")


        # temp_savepath = os.path.join("data", "plugin", "astrbot_plugin_babirthday", "students.json")
        # for proxy_url in proxies:
        #     try:
        #         combined_url = f"{proxy_url}/{self.schaledb_url_cn}"
        #         req = urllib.request.Request(combined_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0."})
        #         with urllib.request.urlopen(req, timeout=60) as response:
        #             raw_data = response.read()
        #             students = json.loads(raw_data)
        #             data_preprocess = []
        #             for i in students:
        #                 data_preprocess.append({
        #                     "Id": i.get("Id"),
        #                     "Name": i.get("Name"),
        #                     "Birthday": i.get("Birthday")
        #                 })
        #             with open(temp_savepath, "wb") as f:
        #                 json_str = json.dumps(data_preprocess, ensure_ascii=False, indent=2)
        #                 f.write(json_str.encode("utf-8"))
        #             yield event.plain_result("成功从 SchaleDB 仓库更新数据！") # 初始化不需要输出，issue。
        #             return
        #     except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        #         logger.error(f"使用代理 {proxy_url} 下载失败: {str(e)}")
        #         continue
        # raise DataDownloadError("从 SchaleDB 仓库拉取数据失败！所有加速链接均无法访问，请检查配置以及网络环境。") # 初始化不需要输出，issue。

    @filter.command("ba数据更新")
    async def update_students_command(self, event: AstrMessageEvent):
        """手动对学生数据进行更新"""
        try:
            yield self.update_students(event)
        except DataDownloadError:
            yield event.plain_result(f"从 SchaleDB 仓库拉取数据失败！所有加速链接均无法访问，请检查配置以及网络环境。")

    @filter.command("ba生日")
    async def get_birthday(self, event: AstrMessageEvent):
        """手动拉取学员生日"""
        try:
            yield self.today_birthdays(event)
        except Exception as e:
            yield event.plain_result(str(e))

    @filter.command("ba本周生日")
    async def week_birthdays(self, event: AstrMessageEvent):
        with open(os.path.join("data", "plugin", "astrbot_plugin_babirthday", "SchaleDB", self.stu_json), "r", encoding="utf-8") as f:
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
            chain.append(Comp.Plain("本周没有学员过生日哦～🎉"))
        else:
            chain.append(Comp.Plain("🎂本周生日学员列表：\n"))
            for date_str, students in ordered_results:
                # 添加日期标题
                chain.append(Comp.Plain(f"\n📅{date_str}："))
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
        self.scheduler.shutdown()