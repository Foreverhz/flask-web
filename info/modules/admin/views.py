import time
from flask import current_app, jsonify
from flask import g
from flask import request, redirect, url_for
from flask import session
from info.models import User, News, Category
from info.utils.image_store import qiniu_image_store
from info.utils.response_code import RET
from . import admin_bp
from flask import render_template
from info.utils.common import login_user_data
from datetime import datetime
from datetime import timedelta
from info import constants, db


@admin_bp.route('/add_category', methods=["POST"])
@login_user_data
def add_category():
    """添加分类"""

    # 1.获取参数
    category_id = request.json.get("id")
    category_name = request.json.get("name")

    # 2.参数校验
    if not category_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    # 3.逻辑处理
    # 分类编辑操作
    if category_id:
        category = None
        try:
            category = Category.query.get(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询分类异常")
        if not category:
            return jsonify(errno=RET.NODATA, errmsg="没有这个分类")

        # 修改分类名称
        category.name = category_name
    else:
        # 添加分类
        category = Category()
        category.name = category_name
        db.session.add(category)

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="修改、添加分类失败")

    return jsonify(errno=RET.OK, errmsg="OK")


@admin_bp.route('/category_type')
@login_user_data
def category_type():
    """新闻分类的类型展示"""
    categories = []
    try:
        categories = Category.query.all()
    except Exception as e:
        current_app.logger.error(e)

    # 移除最新分类
    categories.pop(0)
    category_dict_list = []
    for category in categories if categories else []:
        category_dict_list.append(category.to_dict())

    data = {
        "categories": category_dict_list
    }

    return render_template("admin/news_type.html", data=data)



@admin_bp.route('/news_edit_detail', methods=["post", "get"])
@login_user_data
def news_edit_detail():
    """新闻编辑详情页面"""
    if request.method == "GET":
        news_id = request.args.get("news_id")

        news = None # type:News
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        # 查询所有分类
        categories = []
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)

        # 移除最新的新闻
        categories.pop(0)

        category_dict_list = []
        for category in categories if categories else []:
            # 将分类对象转成字典
            category_dict = category.to_dict()
            #is_select = False
            category_dict["is_selected"] = False
            # 选中当前新闻id
            # 新闻的分类id == 分类id相等才需要选中
            if news.category_id == category.id:
                category_dict["is_selected"] = True

            category_dict_list.append(category_dict)

        news_dict = news.to_dict() if news else None
        data = {
            "news": news_dict,
            "categories": category_dict_list
        }
        return render_template("admin/news_edit_detail.html", data=data)

    # POST请求 新闻编辑
    # POST请求发布新闻
    # 1.获取参数
    news_id = request.form.get("news_id")
    title = request.form.get("title")
    category_id = request.form.get("category_id")
    digest = request.form.get("digest")
    index_image = request.files.get("index_image")
    content = request.form.get("content")
    # 2.校验参数
    # 2.1 判断否为空
    if not all([news_id, title, category_id, digest, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    # 3.逻辑处理
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询新闻数据异常")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在")

    if index_image:
        # 保存图片
        image_data = index_image.read()
        try:
            image_name = qiniu_image_store(image_data)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传新闻图片到七牛云失败")
        # 将新闻的主图片赋值
        news.index_image_url = constants.QINIU_DOMIN_PREFIX + image_name

    news.title = title
    news.category_id = category_id
    news.digest = digest
    news.content = content

    # 将修改保存回数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="修改新闻失败")

    return jsonify(errno=RET.OK, errmsg="编辑新闻成功")


@admin_bp.route('/news_edit')
@login_user_data
def news_edit():
    """新闻编辑页面展示"""
    # 1.获取参数
    p = request.args.get("p", 1)
    keywords = request.args.get("keywords")
    # 获取用户对象
    user = g.user
    # 2.校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    news_list = []
    current_page = 1
    total_page = 1
    # 条件列表
    filter = []
    # 有值表示搜索
    if keywords:
        # 关键字包含于标题的搜索
        filter.append(News.title.contains(keywords))
    if user:
        # 3.逻辑处理
        try:
            paginate = News.query.filter(*filter). \
                order_by(News.create_time.desc()). \
                paginate(p, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

            # 模型列表
            news_list = paginate.items
            current_page = paginate.page
            total_page = paginate.pages

        except Exception as e:
            current_app.logger.error(e)
    # 模型列表转换字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "news_list": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    return render_template("admin/news_edit.html", data=data)


# /admin/news_review_detail?news_id=1
@admin_bp.route('/news_review_detail', methods=["post", "get"])
@login_user_data
def news_review_detail():
    """新闻审核详情页面"""
    if request.method == "GET":
        news_id = request.args.get("news_id")

        news = None # type:News
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        news_dict = news.to_dict() if news else None
        data = {
            "news": news_dict
        }
        return render_template("admin/news_review_detail.html", data=data)

    # POST请求 新闻的审核通过&不通过

    # 1.获取参数
    news_id = request.json.get("news_id")
    action = request.json.get("action")
    # 2.参数校验
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")

    if action not in ["accept", "reject"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数填写错误")

    #3.逻辑处理
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据库异常")

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="新闻不存在")

    # 新闻存在
    if action == "accept":
        # 审核通过
        news.status = 0
    else:
        # 拒绝原因
        reason = request.json.get("reason")
        if reason:
            # 补充拒绝原因
            news.reason = reason
            # 拒绝
            news.status = -1
        else:
            return jsonify(errno=RET.PARAMERR, errmsg="请填写拒绝原因")

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="修改新闻状态失败")

    return jsonify(errno=RET.OK, errmsg="OK")


@admin_bp.route('/news_review')
@login_user_data
def news_review():
    """新闻审核页面展示"""
    # 1.获取参数
    p = request.args.get("p", 1)
    keywords = request.args.get("keywords")
    # 获取用户对象
    user = g.user
    # 2.校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1

    news_list = []
    current_page = 1
    total_page = 1
    # 条件列表
    # 默认条件为审核未通过&未审核的新闻
    filter = [News.status != 0]
    # 有值表示搜索
    if keywords:
        # 关键字包含于标题的搜索
        filter.append(News.title.contains(keywords))
    if user:
        # 3.逻辑处理
        try:
            paginate = News.query.filter(*filter). \
                order_by(News.create_time.desc()). \
                paginate(p, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)

            # 模型列表
            news_list = paginate.items
            current_page = paginate.page
            total_page = paginate.pages

        except Exception as e:
            current_app.logger.error(e)
    # 模型列表转换字典列表
    news_dict_list = []
    for news in news_list if news_list else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "news_list": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    return render_template("admin/news_review.html", data=data)



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

