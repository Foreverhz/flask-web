from flask import g
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template
from redis import StrictRedis
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_session import Session
from config import config_dict
import logging
from logging.handlers import RotatingFileHandler
# 出现MySQLdb导入错误的时候调用下面导入方式
# import pymysql
# 使用install_as_MySQLdb函数将pymysql MySQLdb一起使用
# pymysql.install_as_MySQLdb()

# 将数据库对象暴露给外界调用
# 当app没有值的时候，我们创建一个空的数据库db对象
from info.utils.common import do_index_class, login_user_data


db = SQLAlchemy()
# 将redis数据库对象暴露给外界调用
# # type: StrictRedis作用： 事先声明redis_store以后要保存什么类型的数据
redis_store = None # type: StrictRedis

def create_log(config_name):
    """记录日志的配置函数"""
    # 设置日志的记录等级
    # config_dict[config_name].LOG_LEVEL 获取开发环境日志级别
    logging.basicConfig(level=config_dict[config_name].LOG_LEVEL)  # 调试debug级

    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 *100, backupCount=10)

    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    # INFO manage.py 18 错误信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')

    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)

    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)


# 外界使用方式:  create_app("development") --> 开发模式的app
#              create_app("production")  --> 线上模式的app
def create_app(config_name): # development
    """生产app的工厂方法"""

    # 0.记录日志
    create_log(config_name)
    # 1.创建app对象
    app = Flask(__name__)
    # 2.注册配置信息到app对象
    # config_dict["development"]: DevelopmentConfig 开发模式的配置
    configClass = config_dict[config_name]
    app.config.from_object(configClass)

    # 3. 创建mysql数据库对象
    # 懒加载，延迟加载
    db.init_app(app)

    # 4. 创建redis数据库对象 延迟加载
    global redis_store
    # decode_responses=True 从redis中获取的值是str类
    redis_store = StrictRedis(host=configClass.REDIS_HOST, port=configClass.REDIS_PORT,
                              db=configClass.REDIS_NUM,decode_responses=True)

    # 5. 开启csrf后端保护验证机制
    # 提取cookie中的csrf_token和ajax请求头里面csrf_token进行比较验证操作
    csrf = CSRFProtect(app)

    # 在每一次请求之后 将csrf_token值设置到cookie中
    @app.after_request
    def set_csrf_token(response):
        #1. 生成csrf_token随机值
        csrf_token = generate_csrf()
        #2. 借助响应对象设置csrf_token到cookie中
        response.set_cookie("csrf_token", csrf_token)
        #3. 返回响应对象
        return response

    @app.errorhandler(404)
    @login_user_data
    def page_not_found(e):
        user = g.user
        return render_template("news/404.html",data={"user_info": user.to_dict() if user else None,})

    # 6.创建session拓展类的对象(将session的存储调整到redis中)
    Session(app)

    # 注册自定义过滤器
    app.add_template_filter(do_index_class, "do_index_class")

    # 导入蓝图（延迟导入：解决循环导入文件）
    # 3.注册蓝图
    # 首页蓝图
    from info.modules.index import index_bp
    app.register_blueprint(index_bp)

    # 登录注册模块
    from info.modules.passport import passport_bp
    app.register_blueprint(passport_bp)

    # 新闻模块
    from info.modules.news import news_bp
    app.register_blueprint(news_bp)

    # 用户模块
    from info.modules.profile import profile_bp
    app.register_blueprint(profile_bp)


    return app