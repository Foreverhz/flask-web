from flask import current_app
from flask import g
from flask import request, redirect, url_for
from flask import session

from info.models import User
from . import admin_bp
from flask import render_template
from info.utils.common import login_user_data


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

