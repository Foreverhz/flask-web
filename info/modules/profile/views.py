from flask import current_app
from flask import g, jsonify
from flask import request
from flask import session
from info import db
from info.utils.response_code import RET
from . import profile_bp
from flask import render_template
from info.utils.common import login_user_data
from info.utils.image_store import qiniu_image_store
from info import constants
from info.models import User, Category, News

@profile_bp.route('/user_follow')
@login_user_data
def user_follow():
    """用户关注列表展示"""

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
            # 用户设置dynamic当你只做查询的时候user.followed就是一个查询对象
            paginate = user.followed.paginate(p, constants.USER_FOLLOWED_MAX_COUNT, False)
        except Exception as e:
            current_app.logger.error(e)
        # 模型列表
        users = paginate.items
        current_page = paginate.page
        total_page = paginate.pages

    user_dict_list = []
    for user in users if users else []:
        user_dict_list.append(user.to_dict())

    data = {
        "users": user_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    return render_template("news/user_follow.html", data=data)


@profile_bp.route('/news_list')
@login_user_data
def news_list():
    """新闻审核列表 """

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
    # 3.逻辑处理
    # user.collection_news由于指明了lazy="dynamic"在没有真正使用其数据的时候还是一个查询对象
    try:
        paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
    except Exception as e:
        current_app.logger.error(e)
    # 模型列表
    items = paginate.items
    current_page = paginate.page
    total_page = paginate.pages

    news_dict_list = []
    for news in items if items else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "news_list": news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    return render_template("news/user_news_list.html", data=data)


@profile_bp.route('/news_release', methods=["GET", "POST"])
@login_user_data
def news_release():
    """新闻发布页面展示 发布新闻后端接口"""
    # 获取用户对象
    user = g.user
    if request.method == "GET":
        # 查询分类数据
        try:
            categories = Category.query.all()
        except Exception as e:
            current_app.logger.error(e)
        # 模型列表转字典列表
        category_dict_list = []
        for category in categories if categories else []:
            category_dict_list.append(category.to_dict())
        # 移除最新分类
        category_dict_list.pop(0)
        return render_template("news/user_news_release.html", data={"categories":category_dict_list})

    # POST请求发布新闻
    #1.获取参数
    title = request.form.get("title")
    category_id = request.form.get("category_id")
    digest = request.form.get("digest")
    index_image = request.files.get("index_image")
    content = request.form.get("content")
    source = "个人发布"
    #2.校验参数
    # 2.1 判断否为空
    if not all([title, category_id, digest, index_image, content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 3.逻辑处理
    #保存图片
    image_data = index_image.read()
    try:
        image_name = qiniu_image_store(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传新闻图片到七牛云失败")

    # 创建新闻对象
    news = News()
    news.title = title
    news.digest = digest
    news.category_id = category_id
    news.content = content
    news.index_image_url = constants.QINIU_DOMIN_PREFIX + image_name
    news.source = source
    news.user_id = user.id
    # 新闻处于审核中
    news.status = 1

    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="新闻保存到数据库异常")

    #4.返回值处理
    return jsonify(errno=RET.OK, errmsg="发布新闻成功")


@profile_bp.route('/collection')
@login_user_data
def user_collection():
    """返回用户收藏的列表数据"""
    #1.获取参数
    p = request.args.get("p", 1)
    user = g.user
    #2.校验参数
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1
    #3.逻辑处理
    #user.collection_news由于指明了lazy="dynamic"在没有真正使用其数据的时候还是一个查询对象
    try:
        paginate = user.collection_news.paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
    except Exception as e:
        current_app.logger.error(e)
    # 模型列表
    items = paginate.items
    current_page = paginate.page
    total_page = paginate.pages

    news_dict_list = []
    for news in items if items else []:
        news_dict_list.append(news.to_review_dict())

    data = {
        "collections":news_dict_list,
        "current_page": current_page,
        "total_page": total_page
    }
    #4.返回值处理

    return render_template("news/user_collection.html", data=data)


@profile_bp.route('/pass_info', methods=["GET", "POST"])
@login_user_data
def pass_info():
    """显示修改密码页面  修改密码后端接口"""
    # 获取用户对象
    user = g.user
    if request.method == "GET":
        return render_template("news/user_pass_info.html")

    # POST 修改密码
    # 1.获取参数
    params_dict = request.json
    old_password = params_dict.get("old_password")
    new_password = params_dict.get("new_password")
    # 2.参数校验
    # 2.1 判断否为空
    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不足")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")

    #3.逻辑处理
    if not user.check_passowrd(old_password):
        return jsonify(errno=RET.PARAMERR, errmsg="旧密码填写错误")

    #修改密码
    user.password = new_password

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="修改密码到数据库异常")
    #4.组织返回值
    return jsonify(errno=RET.OK, errmsg="修改密码成功")


# /user/pic_info  --> GET
@profile_bp.route('/pic_info', methods=["GET", "POST"])
@login_user_data
def pic_info():
    """修改用户头像"""
    # 获取用户对象
    user = g.user

    if request.method == "GET":
        return render_template("news/user_pic_info.html")

    #POST 获取用户提交的头像数据进行修改
    # 1.获取参数
    avatar_data = request.files.get("avatar").read()
    # 2.参数校验
    # 2.1 判断否为空
    if not avatar_data:
        return jsonify(errno=RET.NODATA, errmsg="请上传用户头像")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    #3. 逻辑处理
    try:
        image_name = qiniu_image_store(avatar_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="七牛云上传图片失败")

    # 保存图片名称到user对象的avatar_url属性中
    user.avatar_url = image_name # url域名 + image_name (方便后期更改域名)

    # 保存修改操作到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存图片数据异常")

    #4.返回值处理
    full_url = constants.QINIU_DOMIN_PREFIX + image_name
    data = {
        "avatar_url": full_url
    }
    return jsonify(errno=RET.OK, errmsg="修改用户头像成功", data=data)





# /user/user_info  --> GET
@profile_bp.route('/base_info', methods=["GET", "POST"])
@login_user_data
def base_user_info():
    """返回修改用户基本资料页面"""
    # 获取用户对象
    user = g.user

    if request.method == "GET":
        data = {
            "user_info": user.to_dict() if user else None,
        }
        return render_template("news/user_base_info.html", data=data)

    # POST请求修改用户基本资料
    #1.获取参数
    params_dict = request.json
    nick_name = params_dict.get("nick_name")
    signature = params_dict.get("signature")
    gender = params_dict.get("gender")
    #2.参数校验
    # 2.1 判断否为空
    if not all([nick_name, signature, gender]):
        # 返回错误给前端展示
        return jsonify(errno=RET.PARAMERR, errmsg="提交参数不足")
    if gender not in ["MAN", "WOMAN"]:
        return jsonify(errno=RET.PARAMERR, errmsg="性别数据错误")
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    #3.逻辑处理
    user.nick_name = nick_name
    user.signature = signature
    user.gender = gender
    # 注意：修改session数据
    session["nick_name"] = nick_name

    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="修改用户数据异常")

    #4.返回值处理
    return jsonify(errno=RET.OK, errmsg="修改用户数据成功")



# 127.0.0.1:5000/user/info
@profile_bp.route('/info')
@login_user_data
def user_info():
    """用户的基本资料页面"""
    user = g.user
    data = {
        "user_info": user.to_dict() if user else None,
    }
    return render_template("news/user.html", data=data)