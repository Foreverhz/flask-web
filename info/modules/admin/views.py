import time
from flask import current_app
from flask import g
from flask import request, redirect, url_for
from flask import session

from info.models import User
from . import admin_bp
from flask import render_template
from info.utils.common import login_user_data
from datetime import datetime
from datetime import timedelta
from info import constants


@admin_bp.route('/user_list')
@login_user_data
def user_list():
    """用户列表展示"""

    # 1.获取参数
    p = request.args.get("p", 1)
    # 获取用户对象
    user = g.user
    # 2.校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    users = []
    current_page = 1
    total_page = 1
    if user:
        # 3.逻辑处理
        try:
              paginate = User.query.filter(User.is_admin == False).\
                  order_by(User.last_login.desc()).\
                  paginate(p, constants.ADMIN_USER_PAGE_MAX_COUNT, False)

              # 模型列表
              users = paginate.items
              current_page = paginate.page
              total_page = paginate.pages

        except Exception as e:
            current_app.logger.error(e)

    # 用户对象列表转换成字典列表
    user_dict_list = []
    for user in users if users else []:
        user_dict_list.append(user.to_admin_dict())

    data = {
        "users": user_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    return render_template("admin/user_list.html", data=data)


@admin_bp.route('/user_count')
def user_count():
    """用户统计页面展示"""

    # 查询总人数
    total_count = 0
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询月新增数
    mon_count = 0
    try:
        now = time.localtime()
        print(now)
        # 2018-8-31 > 2018-8-01
        # 获取到月初时间
        mon_begin = '%d-%02d-01' % (now.tm_year, now.tm_mon)
        # 日期格式 %Y-%m-%d 年-月-日
        mon_begin_date = datetime.strptime(mon_begin, '%Y-%m-%d')
        # 不是管理员同时用户创建时间晚于月初--->本月新增用户
        mon_count = User.query.filter(User.is_admin == False, User.create_time >= mon_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询日新增数
    day_count = 0
    try:
        # 2018-8-31：12:25 > 2018-8-31：0:0:0
        day_begin = '%d-%02d-%02d' % (now.tm_year, now.tm_mon, now.tm_mday)
        day_begin_date = datetime.strptime(day_begin, '%Y-%m-%d')
        day_count = User.query.filter(User.is_admin == False, User.create_time > day_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询图表信息
    # 获取到当天00:00:00时间

    now_date = datetime.strptime(datetime.now().strftime('%Y-%m-%d'), '%Y-%m-%d')
    # 定义空数组，保存数据
    active_date = []
    active_count = []

    # 依次添加数据，再反转
    for i in range(0, 31):
        # 今天是31号  - 1天 = 30号的 0:0  -- 30号：24：00
        # 今天是31号  - 2天 = 29号的0：0 --- 29：24：00
        begin_date = now_date - timedelta(days=i)
        end_date = begin_date + timedelta(days=i + 1)
        active_date.append(begin_date.strftime('%Y-%m-%d'))
        count = 0
        try:
            # 统计一天中的活跃量
            count = User.query.filter(User.is_admin == False, User.last_login >= begin_date,
                                      User.last_login < end_date).count()
        except Exception as e:
            current_app.logger.error(e)
        active_count.append(count)

    # 进行时间反转
    active_date.reverse()
    # 数据也要反转
    active_count.reverse()

    data = {"total_count": total_count, "mon_count": mon_count, "day_count": day_count, "active_date": active_date,
            "active_count": active_count}

    return render_template('admin/user_count.html', data=data)


# /admin/index
@admin_bp.route('/index', methods=["POST", "GET"])
@login_user_data
def admin_index():
    """管理员首页"""
    user = g.user
    data = {
        "user_info": user.to_dict() if user else None,
    }
    return render_template("admin/index.html",data=data)


# /admin/login
@admin_bp.route('/login', methods=["POST", "GET"])
def admin_login():
    """管理员用户登录接口"""
    if request.method == "GET":
        # 目的: 当管理员已经登录成功再次访问login页面的时候，引导到后台首页
        # 获取session中管理员的用户数据
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin", False)
        if user_id and is_admin:
            # 引导到管理员首页
            return redirect(url_for("admin.admin_index"))

        return render_template("admin/login.html")

    # POST请求管理员用户登录验证
    #1.获取参数
    username = request.form.get("username")
    password = request.form.get("password")

    #2.校验参数
    if not all([username, password]):
        return render_template("admin/login.html",errmsg="参数不足")

    #3.逻辑处理
    try:
        # 查询出管理员用户对象
        user = User.query.filter(User.mobile == username, User.is_admin == True).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template("admin/login.html", errmsg="查询用户对象异常")
    # 用户不存在
    if not user:
        return render_template("admin/login.html", errmsg="用户不存在")

    # 校验密码
    if not user.check_passowrd(password):
        return render_template("admin/login.html", errmsg="密码填写错误")


    # 切记更新管理员数据到session
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["is_admin"] = user.is_admin


    # TODO:跳转到管理员首页
    return redirect(url_for("admin.admin_index"))

