# admin模块
from flask import Blueprint, session, redirect, url_for, request

#1. 创建蓝图对象
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# 切记：让index模块知道有views.py这个文件
from .views import *


@admin_bp.before_request
def before_request():
    """每次请求之前判断是否是管理员"""
    print(request.url)
    if not request.url.endswith("/admin/login"):
        # 获取session中管理员的用户数据
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin",False)
        #不是管理员引导到首页
        if not user_id or not is_admin:
            return redirect("/")
